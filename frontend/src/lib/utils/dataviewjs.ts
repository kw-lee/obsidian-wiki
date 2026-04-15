export type DataviewJsInlineValue =
  | { kind: "text"; text: string }
  | { kind: "link"; path: string; display: string };

export type DataviewJsRenderBlock =
  | { type: "list"; items: DataviewJsInlineValue[] }
  | { type: "table"; headers: string[]; rows: DataviewJsInlineValue[][] }
  | { type: "header"; level: number; text: string }
  | { type: "paragraph"; value: DataviewJsInlineValue }
  | { type: "span"; value: DataviewJsInlineValue }
  | { type: "element"; tag: string; value: DataviewJsInlineValue };

export const DATAVIEW_JS_WORKER_SOURCE = String.raw`(function () {
        const disabledOperation = (name) => () => {
          throw new Error(name + " is disabled inside DataviewJS");
        };
        self.fetch = () =>
          Promise.reject(new Error("Network access is disabled inside DataviewJS"));
        self.importScripts = disabledOperation("importScripts");
        self.WebSocket = undefined;
        self.EventSource = undefined;

        const DATA_ARRAY_TAG = "__dvDataArray";

        function isDataArray(value) {
          return Boolean(value && value[DATA_ARRAY_TAG]);
        }

        function displayFromPath(path) {
          const normalized = String(path || "").split(/[?#^]/)[0];
          const leaf = normalized.split("/").pop() || normalized;
          return leaf.replace(/\.[^/.]+$/, "");
        }

        function createLink(path, display) {
          const normalizedPath = String(path || "").replace(/^\/+/, "");
          return {
            __dvType: "link",
            path: normalizedPath,
            display: display ? String(display) : displayFromPath(normalizedPath),
          };
        }

        function comparableValue(value) {
          if (isDataArray(value)) {
            return comparableValue(value.array());
          }
          if (Array.isArray(value)) {
            return value.map(comparableValue).join("\u0000");
          }
          if (value && value.__dvType === "link") {
            return (value.path + "\u0000" + value.display).toLowerCase();
          }
          if (value && value.file && value.file.path) {
            return String(value.file.path).toLowerCase();
          }
          if (value instanceof Date) {
            return value.getTime();
          }
          if (typeof value === "string") {
            return value.toLowerCase();
          }
          if (value == null) {
            return null;
          }
          return value;
        }

        function compareValues(left, right) {
          const leftValue = comparableValue(left);
          const rightValue = comparableValue(right);
          if (leftValue === rightValue) {
            return 0;
          }
          if (leftValue == null) {
            return 1;
          }
          if (rightValue == null) {
            return -1;
          }
          return leftValue < rightValue ? -1 : 1;
        }

        class DataArrayImpl {
          constructor(values) {
            this.values = Array.from(values || []);
            this[DATA_ARRAY_TAG] = true;
          }

          array() {
            return this.values.slice();
          }

          where(fn) {
            return dataArray(this.values.filter((value, index) => fn(value, index)));
          }

          map(fn) {
            return dataArray(this.values.map((value, index) => fn(value, index)));
          }

          flatMap(fn) {
            const flattened = [];
            for (const [index, value] of this.values.entries()) {
              const mapped = fn(value, index);
              if (isDataArray(mapped)) {
                flattened.push(...mapped.array());
              } else if (Array.isArray(mapped)) {
                flattened.push(...mapped);
              } else {
                flattened.push(mapped);
              }
            }
            return dataArray(flattened);
          }

          sort(keyFn, direction) {
            const getter = typeof keyFn === "function" ? keyFn : (value) => value;
            const multiplier =
              String(direction || "asc").toLowerCase() === "desc" ? -1 : 1;
            return dataArray(
              this.values.slice().sort((left, right) => {
                return compareValues(getter(left), getter(right)) * multiplier;
              }),
            );
          }

          groupBy(keyFn) {
            const groups = [];
            const lookup = new Map();
            for (const value of this.values) {
              const key = keyFn(value);
              const id = JSON.stringify(comparableValue(key));
              if (!lookup.has(id)) {
                const group = { key, rows: [] };
                lookup.set(id, group);
                groups.push(group);
              }
              lookup.get(id).rows.push(value);
            }
            return dataArray(
              groups.map((group) => ({
                key: group.key,
                rows: dataArray(group.rows),
              })),
            );
          }

          distinct(keyFn) {
            const getter = typeof keyFn === "function" ? keyFn : (value) => value;
            const seen = new Set();
            const distinct = [];
            for (const value of this.values) {
              const id = JSON.stringify(comparableValue(getter(value)));
              if (seen.has(id)) {
                continue;
              }
              seen.add(id);
              distinct.push(value);
            }
            return dataArray(distinct);
          }

          concat(other) {
            if (isDataArray(other)) {
              return dataArray(this.values.concat(other.array()));
            }
            if (Array.isArray(other)) {
              return dataArray(this.values.concat(other));
            }
            return dataArray(this.values.concat([other]));
          }

          first() {
            return this.values[0];
          }

          last() {
            return this.values[this.values.length - 1];
          }

          find(fn) {
            return this.values.find((value, index) => fn(value, index));
          }

          some(fn) {
            return this.values.some((value, index) => fn(value, index));
          }

          every(fn) {
            return this.values.every((value, index) => fn(value, index));
          }

          none(fn) {
            return !this.values.some((value, index) => fn(value, index));
          }

          limit(count) {
            return dataArray(this.values.slice(0, Number(count) || 0));
          }

          slice(start, end) {
            return dataArray(this.values.slice(start, end));
          }

          [Symbol.iterator]() {
            return this.values[Symbol.iterator]();
          }
        }

        function swizzle(values, prop) {
          const swizzled = [];
          for (const value of values) {
            const next = value == null ? undefined : value[prop];
            if (isDataArray(next)) {
              swizzled.push(...next.array());
            } else if (Array.isArray(next)) {
              swizzled.push(...next);
            } else {
              swizzled.push(next);
            }
          }
          return dataArray(swizzled);
        }

        function dataArray(values) {
          const target = new DataArrayImpl(values);
          return new Proxy(target, {
            get(current, prop, receiver) {
              if (prop === Symbol.iterator) {
                return current[Symbol.iterator].bind(current);
              }
              if (prop === "length") {
                return current.values.length;
              }
              if (typeof prop === "string" && /^\d+$/.test(prop)) {
                return current.values[Number(prop)];
              }
              if (Reflect.has(current, prop)) {
                const value = Reflect.get(current, prop, receiver);
                return typeof value === "function" ? value.bind(current) : value;
              }
              return swizzle(current.values, prop);
            },
          });
        }

        function toArray(value) {
          if (isDataArray(value)) {
            return value.array();
          }
          if (Array.isArray(value)) {
            return value;
          }
          if (value == null) {
            return [];
          }
          if (value && typeof value !== "string" && value[Symbol.iterator]) {
            return Array.from(value);
          }
          return [value];
        }

        function toText(value) {
          const inline = serializeInline(value);
          return inline.kind === "link" ? inline.display : inline.text;
        }

        function serializeInline(value) {
          if (isDataArray(value)) {
            return serializeInline(value.array());
          }
          if (value == null) {
            return { kind: "text", text: "" };
          }
          if (Array.isArray(value)) {
            return {
              kind: "text",
              text: value.map((item) => toText(item)).filter(Boolean).join(", "),
            };
          }
          if (value && value.__dvType === "link") {
            return {
              kind: "link",
              path: value.path,
              display: value.display || displayFromPath(value.path),
            };
          }
          if (value && value.file && value.file.link) {
            return serializeInline(value.file.link);
          }
          if (value instanceof Date) {
            return { kind: "text", text: value.toISOString() };
          }
          if (typeof value === "object") {
            return { kind: "text", text: JSON.stringify(value) };
          }
          return { kind: "text", text: String(value) };
        }

        function normalizeTagList(tags) {
          return dataArray(Array.isArray(tags) ? tags.map((tag) => String(tag)) : []);
        }

        function maybeNormalizeDate(value) {
          if (typeof value !== "string") {
            return value;
          }
          const trimmed = value.trim();
          if (!trimmed) {
            return value;
          }
          const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(trimmed);
          const isIsoDateTime =
            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$/.test(
              trimmed,
            );
          if (!isDateOnly && !isIsoDateTime) {
            return value;
          }
          const parsed = new Date(isDateOnly ? trimmed + "T00:00:00" : trimmed);
          return Number.isNaN(parsed.getTime()) ? value : parsed;
        }

        function normalizeStructuredValue(value) {
          if (Array.isArray(value)) {
            return value.map(normalizeStructuredValue);
          }
          if (value && typeof value === "object" && !(value instanceof Date)) {
            return Object.fromEntries(
              Object.entries(value).map(([key, entry]) => [
                key,
                normalizeStructuredValue(entry),
              ]),
            );
          }
          return maybeNormalizeDate(value);
        }

        function normalizeTask(task) {
          return {
            path: task.path,
            line: task.line_number,
            lineNumber: task.line_number,
            text: task.text,
            completed: Boolean(task.completed),
            due: task.due_date ? new Date(task.due_date) : null,
            due_date: task.due_date ? new Date(task.due_date) : null,
            priority: task.priority || null,
            link: createLink(task.path),
          };
        }

        function normalizePage(snapshot) {
          const file = {
            name: snapshot.file.name,
            path: snapshot.file.path,
            folder: snapshot.file.folder,
            ext: snapshot.file.ext,
            link: createLink(snapshot.file.link.path, snapshot.file.link.display),
            ctime: snapshot.file.ctime ? new Date(snapshot.file.ctime) : null,
            mtime: snapshot.file.mtime ? new Date(snapshot.file.mtime) : null,
            tags: normalizeTagList(snapshot.file.tags),
            inlinks: dataArray(snapshot.file.inlinks.map((link) => createLink(link.path, link.display))),
            outlinks: dataArray(snapshot.file.outlinks.map((link) => createLink(link.path, link.display))),
            tasks: dataArray(snapshot.file.tasks.map(normalizeTask)),
          };
          return Object.assign(normalizeStructuredValue(snapshot.frontmatter || {}), {
            title: snapshot.title,
            tags: normalizeTagList(snapshot.tags),
            file,
          });
        }

        function buildLookup(pages) {
          const exact = new Map();
          const stems = new Map();
          for (const page of pages) {
            exact.set(page.file.path.toLowerCase(), page);
            const stem = page.file.name.toLowerCase();
            if (!stems.has(stem)) {
              stems.set(stem, []);
            }
            stems.get(stem).push(page);
          }
          return { exact, stems };
        }

        function parentFolder(path) {
          const parts = String(path || "").split("/");
          parts.pop();
          return parts.join("/");
        }

        function sanitizeReference(reference) {
          if (reference == null) {
            return "";
          }
          let normalized = reference;
          if (normalized && normalized.__dvType === "link") {
            normalized = normalized.path;
          }
          normalized = String(normalized).trim();
          if (normalized.startsWith("[[") && normalized.endsWith("]]")) {
            normalized = normalized.slice(2, -2).split("|")[0].trim();
          }
          return normalized.replace(/[#^].*$/, "");
        }

        function resolvePage(reference, currentPath, lookup) {
          const sanitized = sanitizeReference(reference);
          if (!sanitized) {
            return null;
          }

          const candidates = [sanitized];
          if (!/\.[^/]+$/.test(sanitized)) {
            candidates.push(sanitized + ".md");
          }

          const currentFolder = parentFolder(currentPath);
          if (currentFolder) {
            candidates.push(currentFolder + "/" + sanitized);
            if (!/\.[^/]+$/.test(sanitized)) {
              candidates.push(currentFolder + "/" + sanitized + ".md");
            }
          }

          for (const candidate of candidates) {
            const match = lookup.exact.get(candidate.toLowerCase());
            if (match) {
              return match;
            }
          }

          if (!sanitized.includes("/")) {
            const stemMatches = lookup.stems.get(sanitized.toLowerCase());
            if (stemMatches && stemMatches.length === 1) {
              return stemMatches[0];
            }
          }

          return null;
        }

        function filterPages(source, pages) {
          if (source == null || String(source).trim() === "") {
            return pages;
          }
          if (source && source.__dvType === "link") {
            const targetPath = source.path;
            return pages.filter((page) => page.file.path === targetPath);
          }

          const normalized = String(source).trim();
          if (normalized.startsWith("#")) {
            const tag = normalized.slice(1).toLowerCase();
            return pages.filter((page) =>
              page.tags.array().some((value) => {
                const current = String(value).toLowerCase();
                return current === tag || current.startsWith(tag + "/");
              }),
            );
          }

          if (normalized.startsWith('"') && normalized.endsWith('"')) {
            const target = normalized.slice(1, -1).trim().replace(/^\/+|\/+$/g, "");
            if (!target || target === ".") {
              return pages;
            }
            return pages.filter(
              (page) =>
                page.file.path === target ||
                page.file.path.startsWith(target + "/") ||
                page.file.path.startsWith(target + "."),
            );
          }

          throw new Error(
            "DataviewJS currently supports dv.pages() with #tags or quoted folders/paths.",
          );
        }

        function normalizeTag(tag) {
          const candidate = String(tag || "div").toLowerCase();
          return ["div", "p", "span", "strong", "em", "blockquote"].includes(candidate)
            ? candidate
            : "div";
        }

        function markdownList(items) {
          return toArray(items)
            .map((item) => "- " + toText(item))
            .join("\n");
        }

        function markdownTable(headers, rows) {
          const headerLine = toArray(headers).map((item) => toText(item)).join(" | ");
          const dividerLine = toArray(headers)
            .map(() => "---")
            .join(" | ");
          const rowLines = toArray(rows).map((row) =>
            toArray(row)
              .map((item) => toText(item))
              .join(" | "),
          );
          return [headerLine, dividerLine].concat(rowLines).join("\n");
        }

        function buildDataviewApi(pages, currentPath, blocks) {
          const lookup = buildLookup(pages);
          return {
            array(value) {
              if (isDataArray(value)) {
                return value;
              }
              if (Array.isArray(value)) {
                return dataArray(value);
              }
              if (value && typeof value !== "string" && value[Symbol.iterator]) {
                return dataArray(Array.from(value));
              }
              return dataArray(value == null ? [] : [value]);
            },
            current() {
              return resolvePage(currentPath, currentPath, lookup);
            },
            page(path) {
              return resolvePage(path, currentPath, lookup);
            },
            pages(source) {
              return dataArray(filterPages(source, pages));
            },
            pagePaths(source) {
              return dataArray(filterPages(source, pages).map((page) => page.file.path));
            },
            fileLink(path, embed, display) {
              void embed;
              const page = resolvePage(path, currentPath, lookup);
              const resolvedPath = page ? page.file.path : sanitizeReference(path);
              return createLink(resolvedPath, display);
            },
            sectionLink(path, section, display) {
              const base = this.fileLink(path, false, display);
              return createLink(base.path, display || base.display + " > " + String(section || ""));
            },
            blockLink(path, blockId, display) {
              const base = this.fileLink(path, false, display);
              return createLink(base.path, display || base.display + " ^" + String(blockId || ""));
            },
            list(items) {
              blocks.push({
                type: "list",
                items: toArray(items).map(serializeInline),
              });
            },
            table(headers, rows) {
              blocks.push({
                type: "table",
                headers: toArray(headers).map((header) => toText(header)),
                rows: toArray(rows).map((row) => toArray(row).map(serializeInline)),
              });
            },
            header(level, text) {
              blocks.push({
                type: "header",
                level: Math.min(6, Math.max(1, Number(level) || 1)),
                text: toText(text),
              });
            },
            paragraph(value) {
              blocks.push({ type: "paragraph", value: serializeInline(value) });
            },
            span(value) {
              blocks.push({ type: "span", value: serializeInline(value) });
            },
            el(tag, value) {
              blocks.push({
                type: "element",
                tag: normalizeTag(tag),
                value: serializeInline(value),
              });
            },
            markdownList,
            markdownTable,
            compare: compareValues,
            equal(left, right) {
              return compareValues(left, right) === 0;
            },
            isArray(value) {
              return Array.isArray(value) || isDataArray(value);
            },
            clone(value) {
              return JSON.parse(JSON.stringify(value));
            },
          };
        }

        async function execute(code, currentPath, context) {
          const pages = Array.isArray(context.pages)
            ? context.pages.map(normalizePage)
            : [];
          const blocks = [];
          const dv = buildDataviewApi(pages, currentPath, blocks);
          const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
          // Obsidian DataviewJS snippets often rely on sloppy-mode globals.
          const runner = new AsyncFunction("dv", String(code || ""));
          const returned = await runner(dv);
          if (returned !== undefined && blocks.length === 0) {
            blocks.push({ type: "paragraph", value: serializeInline(returned) });
          }
          return blocks;
        }

        self.addEventListener("message", async function (event) {
          const payload = event.data;
          if (!payload || payload.type !== "dataviewjs:execute") {
            return;
          }

          try {
            const blocks = await execute(
              payload.code,
              payload.currentPath,
              payload.context,
            );
            self.postMessage(
              {
                type: "dataviewjs:result",
                id: payload.id,
                blocks,
              },
            );
            self.close();
          } catch (error) {
            self.postMessage(
              {
                type: "dataviewjs:error",
                id: payload.id,
                error:
                  error instanceof Error ? error.message : String(error || "Unknown error"),
              },
            );
            self.close();
          }
        });
      })();`;

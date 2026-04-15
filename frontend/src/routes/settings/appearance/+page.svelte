<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    fetchAppearanceSettings,
    updateAppearanceSettings,
  } from "$lib/api/settings";
  import { getLocale, setLocale, t } from "$lib/i18n/index.svelte";
  import {
    applySavedAppearance,
    previewAppearance,
    resetThemePreview,
  } from "$lib/stores/theme.svelte";
  import type {
    EditorFont,
    ThemePreference,
    ThemePreset,
    UIFont,
  } from "$lib/types";
  import type { Locale } from "$lib/i18n/messages";

  const themePresets: Array<{
    value: ThemePreset;
    titleKey: string;
    copyKey: string;
    accent: string;
    glow: string;
  }> = [
    {
      value: "obsidian",
      titleKey: "appearance.preset.obsidian",
      copyKey: "appearance.preset.obsidianHelp",
      accent: "linear-gradient(135deg, #7fb7ff, #c6b7ff)",
      glow: "rgba(127, 183, 255, 0.28)",
    },
    {
      value: "graphite",
      titleKey: "appearance.preset.graphite",
      copyKey: "appearance.preset.graphiteHelp",
      accent: "linear-gradient(135deg, #6c7687, #a7b6d6)",
      glow: "rgba(108, 118, 135, 0.24)",
    },
    {
      value: "dawn",
      titleKey: "appearance.preset.dawn",
      copyKey: "appearance.preset.dawnHelp",
      accent: "linear-gradient(135deg, #ffb267, #ffd8b1)",
      glow: "rgba(255, 178, 103, 0.24)",
    },
    {
      value: "forest",
      titleKey: "appearance.preset.forest",
      copyKey: "appearance.preset.forestHelp",
      accent: "linear-gradient(135deg, #77c6a2, #b8ecd0)",
      glow: "rgba(119, 198, 162, 0.24)",
    },
  ];

  const uiFontOptions: Array<{
    value: UIFont;
    titleKey: string;
    copyKey: string;
  }> = [
    {
      value: "system",
      titleKey: "appearance.font.ui.system",
      copyKey: "appearance.font.ui.systemHelp",
    },
    {
      value: "nanum-square",
      titleKey: "appearance.font.ui.nanumSquare",
      copyKey: "appearance.font.ui.nanumSquareHelp",
    },
    {
      value: "nanum-square-ac",
      titleKey: "appearance.font.ui.nanumSquareAc",
      copyKey: "appearance.font.ui.nanumSquareAcHelp",
    },
  ];

  const editorFontOptions: Array<{
    value: EditorFont;
    titleKey: string;
    copyKey: string;
  }> = [
    {
      value: "system",
      titleKey: "appearance.font.editor.system",
      copyKey: "appearance.font.editor.systemHelp",
    },
    {
      value: "d2coding",
      titleKey: "appearance.font.editor.d2coding",
      copyKey: "appearance.font.editor.d2codingHelp",
    },
  ];

  let defaultTheme = $state<ThemePreference>("system");
  let themePreset = $state<ThemePreset>("obsidian");
  let uiFont = $state<UIFont>("system");
  let editorFont = $state<EditorFont>("system");
  let locale = $state<Locale>("ko");
  let loading = $state(true);
  let saving = $state(false);
  let previewReady = $state(false);
  let error = $state("");
  let success = $state("");

  onMount(async () => {
    locale = getLocale();
    await loadAppearance();
  });

  onDestroy(() => {
    if (previewReady) {
      resetThemePreview();
    }
  });

  $effect(() => {
    if (!previewReady) return;
    previewAppearance({
      default_theme: defaultTheme,
      theme_preset: themePreset,
      ui_font: uiFont,
      editor_font: editorFont,
    });
  });

  async function loadAppearance() {
    loading = true;
    error = "";
    try {
      const data = await fetchAppearanceSettings();
      defaultTheme = data.default_theme;
      themePreset = data.theme_preset;
      uiFont = data.ui_font;
      editorFont = data.editor_font;
      previewReady = true;
    } catch (err) {
      error = err instanceof Error ? err.message : t("appearance.loadFailed");
    } finally {
      loading = false;
    }
  }

  async function handleSave() {
    saving = true;
    error = "";
    success = "";
    try {
      const appearance = await updateAppearanceSettings({
        default_theme: defaultTheme,
        theme_preset: themePreset,
        ui_font: uiFont,
        editor_font: editorFont,
      });
      applySavedAppearance(appearance);
      success = t("appearance.saveSuccess");
    } catch (err) {
      error = err instanceof Error ? err.message : t("appearance.saveFailed");
    } finally {
      saving = false;
    }
  }

  function handleLocaleChange() {
    setLocale(locale);
    success = t("appearance.language.saved");
  }

  function selectThemeMode(value: ThemePreference) {
    defaultTheme = value;
  }

  function selectThemePreset(value: ThemePreset) {
    themePreset = value;
  }

  function selectUiFont(value: UIFont) {
    uiFont = value;
  }

  function selectEditorFont(value: EditorFont) {
    editorFont = value;
  }

  function previewTitle(index: number) {
    return `${index + 1}. ${t("appearance.previewLine.one")}`;
  }

  function previewSubtitle(index: number) {
    return index % 2 === 0
      ? t("appearance.previewLine.two")
      : t("appearance.previewLine.three");
  }

  function previewStyle(preset: (typeof themePresets)[number]) {
    return `--preset-accent:${preset.accent}; --preset-glow:${preset.glow};`;
  }

  function fontSampleStyle(kind: "ui" | "editor", value: string) {
    return `font-family: var(--font-${kind}-${value});`;
  }
</script>

<section class="panel">
  <div class="panel-header">
    <div>
      <p class="eyebrow">{t("settings.tabs.appearance")}</p>
      <h2>{t("appearance.title")}</h2>
      <p class="copy">{t("appearance.description")}</p>
    </div>
    <button type="button" onclick={handleSave} disabled={saving || loading}>
      {saving ? t("common.saving") : t("common.save")}
    </button>
  </div>

  {#if loading}
    <p class="state">{t("common.loading")}</p>
  {:else}
    <section class="card">
      <div class="section-copy">
        <p class="eyebrow">{t("appearance.mode.title")}</p>
        <h3>{t("appearance.mode.heading")}</h3>
        <p class="copy">{t("appearance.mode.description")}</p>
      </div>

      <div class="choices">
        <label class:active={defaultTheme === "system"}>
          <input
            type="radio"
            checked={defaultTheme === "system"}
            onclick={() => selectThemeMode("system")}
          />
          <div>
            <strong>{t("appearance.theme.system")}</strong>
            <span>{t("appearance.theme.systemHelp")}</span>
          </div>
        </label>
        <label class:active={defaultTheme === "dark"}>
          <input
            type="radio"
            checked={defaultTheme === "dark"}
            onclick={() => selectThemeMode("dark")}
          />
          <div>
            <strong>{t("appearance.theme.dark")}</strong>
            <span>{t("appearance.theme.darkHelp")}</span>
          </div>
        </label>
        <label class:active={defaultTheme === "light"}>
          <input
            type="radio"
            checked={defaultTheme === "light"}
            onclick={() => selectThemeMode("light")}
          />
          <div>
            <strong>{t("appearance.theme.light")}</strong>
            <span>{t("appearance.theme.lightHelp")}</span>
          </div>
        </label>
      </div>
    </section>

    <section class="card">
      <div class="section-copy">
        <p class="eyebrow">{t("appearance.preset.title")}</p>
        <h3>{t("appearance.preset.heading")}</h3>
        <p class="copy">{t("appearance.preset.description")}</p>
      </div>

      <div class="preset-grid">
        {#each themePresets as preset, index}
          <button
            type="button"
            class="preset-card"
            class:active={themePreset === preset.value}
            style={previewStyle(preset)}
            onclick={() => selectThemePreset(preset.value)}
          >
            <div class="preset-hero">
              <div class="preset-glow"></div>
              <div class="preset-window">
                <span class="preset-dot"></span>
                <div class="preset-preview">
                  <span class="preset-bar strong"></span>
                  <strong class="preset-label">{previewTitle(index)}</strong>
                  <span class="preset-bar"></span>
                  <span class="preset-label muted"
                    >{previewSubtitle(index)}</span
                  >
                </div>
              </div>
            </div>
            <div class="preset-copy">
              <strong>{t(preset.titleKey)}</strong>
              <span>{t(preset.copyKey)}</span>
            </div>
          </button>
        {/each}
      </div>
    </section>

    <section class="card">
      <div class="section-copy">
        <p class="eyebrow">{t("appearance.font.title")}</p>
        <h3>{t("appearance.font.heading")}</h3>
        <p class="copy">{t("appearance.font.description")}</p>
      </div>

      <div class="font-sections">
        <div class="font-group">
          <div class="font-group-copy">
            <strong>{t("appearance.font.uiTitle")}</strong>
            <span>{t("appearance.font.uiDescription")}</span>
          </div>
          <div class="font-grid">
            {#each uiFontOptions as option}
              <button
                type="button"
                class="font-card"
                class:active={uiFont === option.value}
                onclick={() => selectUiFont(option.value)}
              >
                <div class="font-card-copy">
                  <strong>{t(option.titleKey)}</strong>
                  <span>{t(option.copyKey)}</span>
                </div>
                <div
                  class="font-sample"
                  style={fontSampleStyle("ui", option.value)}
                >
                  <strong>{t("appearance.font.uiSampleTitle")}</strong>
                  <span>{t("appearance.font.uiSampleBody")}</span>
                </div>
              </button>
            {/each}
          </div>
        </div>

        <div class="font-group">
          <div class="font-group-copy">
            <strong>{t("appearance.font.editorTitle")}</strong>
            <span>{t("appearance.font.editorDescription")}</span>
          </div>
          <div class="font-grid compact">
            {#each editorFontOptions as option}
              <button
                type="button"
                class="font-card"
                class:active={editorFont === option.value}
                onclick={() => selectEditorFont(option.value)}
              >
                <div class="font-card-copy">
                  <strong>{t(option.titleKey)}</strong>
                  <span>{t(option.copyKey)}</span>
                </div>
                <div
                  class="font-sample editor"
                  style={fontSampleStyle("editor", option.value)}
                >
                  <code>{t("appearance.font.editorSample")}</code>
                </div>
              </button>
            {/each}
          </div>
        </div>
      </div>
    </section>

    <section class="locale-card">
      <div>
        <p class="eyebrow">{t("common.language")}</p>
        <h3>{t("appearance.language.title")}</h3>
        <p class="copy">{t("appearance.language.description")}</p>
      </div>
      <div class="locale-row">
        <select bind:value={locale}>
          <option value="ko">{t("locale.ko")}</option>
          <option value="en">{t("locale.en")}</option>
        </select>
        <button type="button" class="secondary" onclick={handleLocaleChange}>
          {t("common.save")}
        </button>
      </div>
    </section>
  {/if}

  {#if error}
    <p class="feedback error">{error}</p>
  {/if}
  {#if success}
    <p class="feedback success">{success}</p>
  {/if}
</section>

<style>
  .panel {
    max-width: 960px;
    display: grid;
    gap: 1.5rem;
  }

  .panel-header,
  .card,
  .locale-card {
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 24px;
    background: var(--bg-panel);
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(18px);
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .card {
    display: grid;
    gap: 1.25rem;
  }

  .section-copy {
    display: grid;
    gap: 0.45rem;
  }

  .eyebrow {
    margin: 0;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  h2,
  h3 {
    margin: 0;
  }

  .copy,
  .state {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.6;
  }

  button {
    padding: 0.85rem 1.25rem;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: white;
    font: inherit;
    cursor: pointer;
    transition:
      transform 0.18s ease,
      box-shadow 0.18s ease,
      opacity 0.18s ease;
  }

  button:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 10px 24px color-mix(in srgb, var(--accent) 26%, transparent);
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button.secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .choices {
    display: grid;
    gap: 0.9rem;
  }

  .choices label,
  .locale-card {
    display: grid;
    gap: 1rem;
  }

  .choices label {
    grid-template-columns: auto 1fr;
    align-items: start;
    cursor: pointer;
    padding: 1.1rem 1.15rem;
    border: 1px solid var(--border);
    border-radius: 18px;
    background: color-mix(in srgb, var(--bg-secondary) 84%, transparent);
    transition:
      border-color 0.2s ease,
      background 0.2s ease,
      transform 0.2s ease;
  }

  .choices label:hover {
    transform: translateY(-1px);
  }

  .choices label.active {
    border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
    background: color-mix(in srgb, var(--accent) 12%, var(--bg-secondary));
  }

  .choices strong {
    display: block;
    margin-bottom: 0.25rem;
  }

  .choices span {
    color: var(--text-secondary);
  }

  .preset-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .preset-card {
    padding: 1rem;
    border-radius: 22px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-secondary) 90%, transparent);
    color: inherit;
    text-align: left;
    display: grid;
    gap: 0.9rem;
  }

  .preset-card.active {
    border-color: color-mix(in srgb, var(--accent) 34%, var(--border));
    background: color-mix(in srgb, var(--accent) 11%, var(--bg-secondary));
    box-shadow: 0 18px 40px color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .preset-hero {
    position: relative;
    min-height: 8.5rem;
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    background:
      radial-gradient(circle at top left, var(--preset-glow), transparent 34%),
      linear-gradient(
        160deg,
        color-mix(in srgb, var(--bg-primary) 70%, transparent),
        var(--bg-tertiary)
      );
  }

  .preset-glow {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--preset-accent), transparent 68%);
    opacity: 0.75;
  }

  .preset-window {
    position: absolute;
    inset: 1rem;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, white 10%, var(--border));
    background: color-mix(in srgb, var(--bg-secondary) 86%, transparent);
    padding: 1rem;
    display: grid;
    align-content: start;
    gap: 0.75rem;
    backdrop-filter: blur(12px);
  }

  .preset-dot {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 999px;
    background: white;
    opacity: 0.9;
  }

  .preset-preview {
    display: grid;
    gap: 0.35rem;
    align-content: start;
  }

  .preset-bar {
    display: block;
    height: 0.65rem;
    width: 70%;
    border-radius: 999px;
    background: color-mix(in srgb, white 14%, var(--bg-tertiary));
  }

  .preset-bar.strong {
    width: 54%;
    background: color-mix(in srgb, white 12%, var(--accent));
  }

  .preset-label {
    color: var(--text-primary);
    font-size: 0.95rem;
    line-height: 1.35;
  }

  .preset-label.muted {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .preset-copy {
    display: grid;
    gap: 0.25rem;
  }

  .preset-copy span {
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .font-sections,
  .font-group,
  .font-group-copy {
    display: grid;
  }

  .font-sections {
    gap: 1.5rem;
  }

  .font-group {
    gap: 0.85rem;
  }

  .font-group-copy {
    gap: 0.3rem;
  }

  .font-group-copy span,
  .font-card-copy span {
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .font-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .font-grid.compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .font-card {
    padding: 1rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-secondary) 90%, transparent);
    color: inherit;
    text-align: left;
    display: grid;
    gap: 0.9rem;
  }

  .font-card.active {
    border-color: color-mix(in srgb, var(--accent) 34%, var(--border));
    background: color-mix(in srgb, var(--accent) 10%, var(--bg-secondary));
    box-shadow: 0 18px 40px color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .font-card-copy {
    display: grid;
    gap: 0.25rem;
  }

  .font-sample {
    display: grid;
    gap: 0.35rem;
    padding: 0.95rem 1rem;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--border) 78%, transparent);
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--bg-primary) 76%, transparent),
      color-mix(in srgb, var(--bg-secondary) 92%, transparent)
    );
    box-shadow: inset 0 1px 0 color-mix(in srgb, white 10%, transparent);
  }

  .font-sample strong {
    font-size: 1rem;
    line-height: 1.4;
  }

  .font-sample span {
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .font-sample.editor {
    min-height: 4.75rem;
    align-content: center;
  }

  .font-sample code {
    font: inherit;
    color: var(--text-primary);
    white-space: nowrap;
  }

  .locale-row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  select {
    flex: 1;
    padding: 0.85rem 1rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--bg-input);
    color: var(--text-primary);
  }

  .feedback {
    margin: 0;
    padding: 0.85rem 1rem;
    border-radius: 14px;
  }

  .feedback.error {
    background: color-mix(in srgb, var(--error) 14%, transparent);
    color: var(--error);
  }

  .feedback.success {
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    color: var(--text-primary);
  }

  @media (max-width: 720px) {
    .panel-header,
    .locale-row {
      flex-direction: column;
    }

    .preset-grid {
      grid-template-columns: 1fr;
    }

    .font-grid,
    .font-grid.compact {
      grid-template-columns: 1fr;
    }

    button,
    .preset-card,
    .font-card {
      width: 100%;
    }
  }
</style>

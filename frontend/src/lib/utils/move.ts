import type { MovePathResult } from "$lib/types";

export interface MoveToastDescriptor {
  key: "fileExplorer.moveSuccess" | "fileExplorer.moveRewriteSuccess" | "fileExplorer.moveRewriteNone";
  values: Record<string, string | number>;
}

export function describeMoveToast(
  sourcePath: string,
  destinationPath: string,
  result: MovePathResult,
): MoveToastDescriptor {
  if (result.rewrite_links && result.rewritten_links > 0) {
    return {
      key: "fileExplorer.moveRewriteSuccess",
      values: {
        source: sourcePath,
        destination: destinationPath,
        links: result.rewritten_links,
        files: result.rewritten_paths.length,
      },
    };
  }

  if (result.rewrite_links) {
    return {
      key: "fileExplorer.moveRewriteNone",
      values: {
        source: sourcePath,
        destination: destinationPath,
      },
    };
  }

  return {
    key: "fileExplorer.moveSuccess",
    values: {
      source: sourcePath,
      destination: destinationPath,
    },
  };
}

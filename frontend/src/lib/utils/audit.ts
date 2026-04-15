type AuditLike = {
  action: string;
  path: string;
};

export function getAuditTargetPath(entry: AuditLike): string | null {
  const rawPath = entry.path.trim();
  if (!rawPath) {
    return null;
  }

  switch (entry.action) {
    case "wiki.create":
    case "wiki.update":
    case "attachment.upload":
      return rawPath;
    case "wiki.move": {
      const [, destination] = rawPath.split(/\s*->\s*/, 2);
      return destination?.trim() || null;
    }
    default:
      return null;
  }
}

export function shortCommitSha(commitSha: string | null): string | null {
  return commitSha ? commitSha.slice(0, 8) : null;
}

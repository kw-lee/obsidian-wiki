<script lang="ts">
  import type { ResolvedWikiLink } from "$lib/types";
  import LinksPanel from "./LinksPanel.svelte";

  let {
    docPath,
    outgoingLinks = [],
    onnavigate,
  }: {
    docPath: string;
    outgoingLinks?: ResolvedWikiLink[];
    onnavigate: (path: string) => void;
  } = $props();
</script>

<LinksPanel {docPath} {outgoingLinks} {onnavigate} />

<script lang="ts">
  import type { ResolvedWikiLink } from "$lib/types";
  import LinksPanel from "./LinksPanel.svelte";

  let {
    docPath,
    outgoingLinks = [],
    selectedTab = "backlinks",
    onnavigate,
    ontabchange = undefined,
  }: {
    docPath: string;
    outgoingLinks?: ResolvedWikiLink[];
    selectedTab?: "backlinks" | "frontlinks";
    onnavigate: (path: string) => void;
    ontabchange?: (tab: "backlinks" | "frontlinks") => void;
  } = $props();
</script>

<LinksPanel
  {docPath}
  {outgoingLinks}
  {selectedTab}
  {onnavigate}
  {ontabchange}
/>

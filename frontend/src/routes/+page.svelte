<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import WikiWorkspace from "$lib/components/WikiWorkspace.svelte";
  import { buildWikiRoute } from "$lib/utils/routes";

  onMount(() => {
    const legacyDoc = page.url.searchParams.get("doc");
    if (legacyDoc) {
      void goto(buildWikiRoute(legacyDoc), { replaceState: true });
    }
  });
</script>

<WikiWorkspace />

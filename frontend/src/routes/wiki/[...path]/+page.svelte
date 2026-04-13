<script lang="ts">
  import { page } from "$app/state";
  import WikiWorkspace from "$lib/components/WikiWorkspace.svelte";
</script>

<WikiWorkspace initialPath={page.params.path} />

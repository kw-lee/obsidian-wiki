<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { initAuth } from '$lib/stores/auth.svelte';
	import { initTheme } from '$lib/stores/theme.svelte';

	let { children } = $props();

	onMount(() => {
		initAuth();
		initTheme();
	});
</script>

<svelte:head>
	<title>Obsidian Wiki</title>
</svelte:head>

{@render children()}

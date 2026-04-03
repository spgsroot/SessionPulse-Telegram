<script lang="ts">
  import { accounts, summary } from '$lib/stores/accounts';
  import AccountCard from '$lib/components/AccountCard.svelte';
  import StateIndicator from '$lib/components/StateIndicator.svelte';

  let filter = $state('all');

  const filtered = $derived(
    filter === 'all'
      ? $accounts
      : $accounts.filter(a => a.state === filter)
  );

  const states = $derived(
    Object.entries($summary.by_state).sort((a, b) => b[1] - a[1])
  );
</script>

<svelte:head>
  <title>Accounts - SessionPulse</title>
</svelte:head>

<div class="section">
  <div class="section-header">
    <h1>Accounts ({$summary.total})</h1>
  </div>

  <div class="filters">
    <button class="filter-btn" class:active={filter === 'all'} onclick={() => filter = 'all'}>
      All ({$summary.total})
    </button>
    {#each states as [state, count]}
      <button class="filter-btn" class:active={filter === state} onclick={() => filter = state}>
        <StateIndicator {state} size="sm" /> ({count})
      </button>
    {/each}
  </div>
</div>

<div class="grid-2">
  {#each filtered as account (account.phone)}
    <AccountCard {account} />
  {/each}
</div>

{#if filtered.length === 0}
  <div class="empty">No accounts match filter "{filter}"</div>
{/if}

<style>
  .filters {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }
  .filter-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.82em;
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-btn:hover {
    border-color: var(--border-hover);
    background: var(--bg-surface);
  }
  .filter-btn.active {
    border-color: var(--accent);
    background: rgba(137, 180, 250, 0.1);
    color: var(--accent);
  }
  .empty {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
    background: var(--bg-surface);
    border: 1px dashed var(--border);
    border-radius: 10px;
  }
</style>

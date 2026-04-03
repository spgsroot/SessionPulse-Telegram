<script lang="ts">
  import { onMount } from 'svelte';
  import { accounts, summary } from '$lib/stores/accounts';
  import { firingCount } from '$lib/stores/alerts';
  import { api } from '$lib/api/client';
  import type { PipelineHealth } from '$lib/api/client';
  import AccountCard from '$lib/components/AccountCard.svelte';
  import AlertBanner from '$lib/components/AlertBanner.svelte';
  import PipelineFlow from '$lib/components/PipelineFlow.svelte';
  import { stateColor } from '$lib/utils/colors';

  let pipeline: PipelineHealth | null = $state(null);

  onMount(async () => {
    try {
      pipeline = await api.pipeline.health();
    } catch (e) {
      console.error('Failed to load pipeline:', e);
    }

    // Auto-refresh every 15s
    const interval = setInterval(async () => {
      try {
        const [accRes, pipeRes] = await Promise.all([
          api.accounts.list(),
          api.pipeline.health()
        ]);
        accounts.set(accRes.accounts);
        pipeline = pipeRes;
      } catch { /* ignore */ }
    }, 15000);

    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>SessionPulse - Overview</title>
</svelte:head>

<AlertBanner />

<div class="section">
  <h1>Overview</h1>
</div>

<!-- Summary stats -->
<div class="grid-3 section">
  <div class="stat-card">
    <span class="value">{$summary.total}</span>
    <span class="label">Total Accounts</span>
  </div>
  <div class="stat-card">
    <span class="value" style="color: var(--green)">{$summary.by_state['monitoring'] || 0}</span>
    <span class="label">Monitoring</span>
  </div>
  <div class="stat-card">
    <span class="value" style="color: var(--red)">{($summary.by_state['error'] || 0) + ($summary.by_state['banned'] || 0)}</span>
    <span class="label">Errors</span>
  </div>
  <div class="stat-card">
    <span class="value" style="color: var(--yellow)">{$summary.by_state['throttled'] || 0}</span>
    <span class="label">Throttled</span>
  </div>
  <div class="stat-card">
    <span class="value" style="color: var(--text-muted)">{$summary.by_state['stopped'] || 0}</span>
    <span class="label">Stopped</span>
  </div>
  <div class="stat-card">
    <span class="value" style="color: {$firingCount > 0 ? 'var(--red)' : 'var(--green)'}">{$firingCount}</span>
    <span class="label">Active Alerts</span>
  </div>
</div>

<!-- Pipeline -->
{#if pipeline}
  <div class="section">
    <PipelineFlow {pipeline} />
  </div>
{/if}

<!-- Account grid -->
<div class="section">
  <div class="section-header">
    <h2>Accounts</h2>
    <a href="/accounts" class="btn">View All</a>
  </div>
  <div class="grid-2">
    {#each $accounts.slice(0, 6) as account (account.phone)}
      <AccountCard {account} />
    {/each}
  </div>
  {#if $accounts.length === 0}
    <div class="empty-state">No accounts being monitored</div>
  {/if}
</div>

<style>
  .empty-state {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
    background: var(--bg-surface);
    border: 1px dashed var(--border);
    border-radius: 10px;
  }
</style>

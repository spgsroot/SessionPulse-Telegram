<script lang="ts">
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api/client';
  import type { AccountState, TimelineEvent } from '$lib/api/client';
  import StateIndicator from '$lib/components/StateIndicator.svelte';
  import Timeline from '$lib/components/Timeline.svelte';
  import { maskPhone, timeAgo, formatRate, formatDuration } from '$lib/utils/formatters';
  import { connectWS, disconnectWS, wsMessages } from '$lib/stores/websocket';

  const phone = $derived(decodeURIComponent($page.params.phone));

  let account: AccountState | null = $state(null);
  let events: TimelineEvent[] = $state([]);
  let totalEvents = $state(0);
  let loading = $state(true);
  let showFullPhone = $state(false);

  onMount(async () => {
    try {
      const [accData, tlData] = await Promise.all([
        api.accounts.get(phone),
        api.accounts.timeline(phone, 50)
      ]);
      account = accData;
      events = tlData.events;
      totalEvents = tlData.total;
    } catch (e) {
      console.error('Load failed:', e);
    }
    loading = false;

    // Listen for real-time events on this account's timeline
    const unsub = wsMessages.subscribe((msg) => {
      if (!msg) return;
      if (msg.type === 'event' && msg.event) {
        const ev = msg.event as TimelineEvent;
        if (ev.entity_id === phone) {
          events = [ev, ...events].slice(0, 200);
          totalEvents++;
        }
      }
      if (msg.type === 'state_change' && msg.phone === phone) {
        if (account) {
          account = {
            ...account,
            state: msg.new_state as string,
            previous_state: msg.previous_state as string,
            error_message: (msg.error || '') as string
          };
        }
      }
    });

    return () => unsub();
  });

  function sinceNow(iso: string): string {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    return formatDuration(Math.max(0, diff));
  }

  async function loadMore() {
    const tlData = await api.accounts.timeline(phone, 50, events.length);
    events = [...events, ...tlData.events];
  }
</script>

<svelte:head>
  <title>{maskPhone(phone)} - SessionPulse</title>
</svelte:head>

{#if loading}
  <div class="loading">Loading...</div>
{:else if account}
  <div class="header">
    <a href="/accounts" class="back">&larr; Accounts</a>
    <div class="header-main">
      <h1 class="phone-title" onclick={() => showFullPhone = !showFullPhone}>
        {showFullPhone ? account.phone : maskPhone(account.phone)}
      </h1>
      <StateIndicator state={account.state} size="lg" />
    </div>
  </div>

  <!-- Metrics row -->
  <div class="grid-3 section">
    <div class="stat-card">
      <span class="value">{formatRate(account.metrics.messages_1m * 60)}</span>
      <span class="label">Messages / min</span>
    </div>
    <div class="stat-card">
      <span class="value">{account.metrics.active_channels}</span>
      <span class="label">Active Channels</span>
    </div>
    <div class="stat-card">
      <span class="value">{account.metrics.errors_1h}</span>
      <span class="label">Errors (1h)</span>
    </div>
    <div class="stat-card">
      <span class="value">{sinceNow(account.state_since)}</span>
      <span class="label">In State Since</span>
    </div>
    <div class="stat-card">
      <span class="value">{timeAgo(account.last_event_at)}</span>
      <span class="label">Last Event</span>
    </div>
    <div class="stat-card">
      <span class="value">{formatRate(account.metrics.reactions_1m * 60)}</span>
      <span class="label">Reactions / min</span>
    </div>
  </div>

  {#if account.error_message}
    <div class="error-banner section">
      <strong>Error:</strong> {account.error_message}
    </div>
  {/if}

  <!-- Timeline -->
  <div class="section">
    <div class="section-header">
      <h2>Timeline ({totalEvents} events)</h2>
    </div>
    <Timeline {events} />
    {#if events.length < totalEvents}
      <button class="btn load-more" onclick={loadMore}>Load More</button>
    {/if}
  </div>
{:else}
  <div class="error-state">Account not found: {phone}</div>
{/if}

<style>
  .header {
    margin-bottom: 20px;
  }
  .back {
    font-size: 0.85em;
    color: var(--text-muted);
    text-decoration: none;
    display: inline-block;
    margin-bottom: 8px;
  }
  .back:hover { color: var(--accent); }
  .header-main {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .phone-title {
    font-family: 'JetBrains Mono', monospace;
    cursor: pointer;
    user-select: none;
  }
  .error-banner {
    background: rgba(243, 139, 168, 0.08);
    border: 1px solid rgba(243, 139, 168, 0.2);
    color: #f38ba8;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.88em;
  }
  .load-more {
    width: 100%;
    margin-top: 8px;
    justify-content: center;
  }
  .loading, .error-state {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
  }
</style>

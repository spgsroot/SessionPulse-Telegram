<script lang="ts">
  import '../app.css';
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { connectWS, disconnectWS } from '$lib/stores/websocket';
  import { wsMessages } from '$lib/stores/websocket';
  import { accounts } from '$lib/stores/accounts';
  import { alerts } from '$lib/stores/alerts';
  import { firingCount } from '$lib/stores/alerts';
  import { updateAccountState } from '$lib/stores/accounts';
  import { api } from '$lib/api/client';
  import ConnectionStatus from '$lib/components/ConnectionStatus.svelte';

  let { children } = $props();

  const nav = [
    { href: '/', label: 'Overview' },
    { href: '/accounts', label: 'Accounts' },
    { href: '/pipeline', label: 'Pipeline' },
    { href: '/alerts', label: 'Alerts' }
  ];

  onMount(async () => {
    // Initial data load
    try {
      const [accRes, alertRes] = await Promise.all([
        api.accounts.list(),
        api.alerts.list()
      ]);
      accounts.set(accRes.accounts);
      alerts.set(alertRes.alerts);
    } catch (e) {
      console.error('Initial load failed:', e);
    }

    // Connect WebSocket
    connectWS('accounts');

    // Process WS messages
    const unsub = wsMessages.subscribe((msg) => {
      if (!msg) return;
      if (msg.type === 'state_change') {
        updateAccountState(
          msg.phone as string,
          msg.new_state as string,
          { previous_state: msg.previous_state, error_message: msg.error || '' }
        );
      }
    });

    return () => unsub();
  });

  onDestroy(() => {
    disconnectWS();
  });
</script>

<div class="app">
  <nav class="navbar">
    <div class="container nav-inner">
      <a href="/" class="logo">
        <span class="logo-icon">&#x1F4E1;</span>
        <span class="logo-text">SessionPulse</span>
      </a>
      <div class="nav-links">
        {#each nav as item}
          <a
            href={item.href}
            class="nav-link"
            class:active={$page.url.pathname === item.href}
          >
            {item.label}
            {#if item.label === 'Alerts' && $firingCount > 0}
              <span class="nav-badge">{$firingCount}</span>
            {/if}
          </a>
        {/each}
      </div>
      <ConnectionStatus />
    </div>
  </nav>

  <main class="container main">
    {@render children()}
  </main>
</div>

<style>
  .app {
    min-height: 100vh;
  }
  .navbar {
    background: #181825;
    border-bottom: 1px solid #313244;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(8px);
  }
  .nav-inner {
    display: flex;
    align-items: center;
    height: 52px;
    gap: 24px;
  }
  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: #cdd6f4;
    font-weight: 700;
    font-size: 1.05em;
    flex-shrink: 0;
  }
  .logo-icon { font-size: 1.2em; }
  .nav-links {
    display: flex;
    gap: 4px;
    flex: 1;
  }
  .nav-link {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.88em;
    font-weight: 500;
    color: #a6adc8;
    text-decoration: none;
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .nav-link:hover {
    background: rgba(137, 180, 250, 0.08);
    color: #cdd6f4;
    text-decoration: none;
  }
  .nav-link.active {
    background: rgba(137, 180, 250, 0.12);
    color: #89b4fa;
  }
  .nav-badge {
    background: #ef4444;
    color: white;
    font-size: 0.7em;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 10px;
    min-width: 18px;
    text-align: center;
  }
  .main {
    padding-top: 20px;
    padding-bottom: 40px;
  }
</style>

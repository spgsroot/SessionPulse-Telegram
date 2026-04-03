<script lang="ts">
  import { wsConnected } from '$lib/stores/websocket';
</script>

<div class="status" class:connected={$wsConnected} class:disconnected={!$wsConnected}>
  <span class="dot"></span>
  <span class="text">{$wsConnected ? 'Live' : 'Disconnected'}</span>
</div>

<style>
  .status {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.75em;
    padding: 3px 8px;
    border-radius: 12px;
  }
  .connected {
    background: rgba(34, 197, 94, 0.12);
    color: #22c55e;
  }
  .disconnected {
    background: rgba(239, 68, 68, 0.12);
    color: #ef4444;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }
  .connected .dot {
    animation: pulse 2s ease-in-out infinite;
  }
  .text {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
</style>

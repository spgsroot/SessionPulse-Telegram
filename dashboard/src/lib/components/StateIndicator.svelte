<script lang="ts">
  import { stateColor, stateIcon } from '$lib/utils/colors';

  let { state, size = 'md' }: { state: string; size?: 'sm' | 'md' | 'lg' } = $props();

  const sizes = { sm: '8px', md: '12px', lg: '16px' };
</script>

<span
  class="state-indicator"
  title={state}
  style="--dot-size: {sizes[size]}; --dot-color: {stateColor(state)}"
>
  <span class="dot"></span>
  <span class="label">{state}</span>
</span>

<style>
  .state-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .dot {
    width: var(--dot-size);
    height: var(--dot-size);
    border-radius: 50%;
    background: var(--dot-color);
    box-shadow: 0 0 6px var(--dot-color);
    flex-shrink: 0;
  }
  .label {
    font-size: 0.85em;
    color: var(--dot-color);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
</style>

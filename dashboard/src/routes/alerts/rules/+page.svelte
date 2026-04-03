<script lang="ts">
  import { onMount } from 'svelte';
  import { SEVERITY_COLORS } from '$lib/utils/colors';

  interface AlertRule {
    name: string;
    description: string;
    condition_field: string;
    condition_op: string;
    condition_value: string;
    entity_type: string;
    severity: string;
    cooldown_seconds: number;
    for_seconds: number;
    enabled: boolean;
    message_template: string;
    metric_name: string;
    metric_window: string;
  }

  let rules: AlertRule[] = $state([]);
  let loading = $state(true);
  let editingRule: string | null = $state(null);
  let showCreate = $state(false);

  // New rule form
  let newRule: Partial<AlertRule> = $state({
    name: '',
    description: '',
    condition_field: 'state',
    condition_op: '==',
    condition_value: '',
    entity_type: 'account',
    severity: 'warning',
    cooldown_seconds: 300,
    for_seconds: 0,
    enabled: true,
    message_template: '',
    metric_name: '',
    metric_window: '1m',
  });

  onMount(async () => {
    await refresh();
    loading = false;
  });

  async function refresh() {
    try {
      const res = await fetch('/api/v1/alerts/rules');
      const data = await res.json();
      rules = data.rules || [];
    } catch (e) {
      console.error('Failed to load rules:', e);
    }
  }

  async function toggleRule(name: string, enabled: boolean) {
    try {
      await fetch(`/api/v1/alerts/rules/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      await refresh();
    } catch (e) {
      console.error('Toggle failed:', e);
    }
  }

  async function deleteRule(name: string) {
    try {
      await fetch(`/api/v1/alerts/rules/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      await refresh();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  async function createRule() {
    if (!newRule.name) return;
    try {
      await fetch('/api/v1/alerts/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRule),
      });
      showCreate = false;
      newRule = {
        name: '', description: '', condition_field: 'state', condition_op: '==',
        condition_value: '', entity_type: 'account', severity: 'warning',
        cooldown_seconds: 300, for_seconds: 0, enabled: true, message_template: '',
        metric_name: '', metric_window: '1m',
      };
      await refresh();
    } catch (e) {
      console.error('Create failed:', e);
    }
  }

  async function saveEdit(name: string, updates: Partial<AlertRule>) {
    try {
      await fetch(`/api/v1/alerts/rules/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      editingRule = null;
      await refresh();
    } catch (e) {
      console.error('Save failed:', e);
    }
  }
</script>

<svelte:head>
  <title>Alert Rules - SessionPulse</title>
</svelte:head>

<div class="section">
  <div class="section-header">
    <div>
      <h1>Alert Rules</h1>
      <a href="/alerts" class="back-link">&larr; Back to Alerts</a>
    </div>
    <button class="btn btn-primary" onclick={() => showCreate = !showCreate}>
      {showCreate ? 'Cancel' : '+ New Rule'}
    </button>
  </div>
</div>

<!-- Create form -->
{#if showCreate}
  <div class="card create-form section">
    <h3>Create New Rule</h3>
    <div class="form-grid">
      <div class="field">
        <label>Name</label>
        <input type="text" bind:value={newRule.name} placeholder="my_custom_rule" />
      </div>
      <div class="field">
        <label>Description</label>
        <input type="text" bind:value={newRule.description} placeholder="What this rule detects" />
      </div>
      <div class="field">
        <label>Entity Type</label>
        <select bind:value={newRule.entity_type}>
          <option value="account">Account</option>
          <option value="metric">Metric</option>
        </select>
      </div>
      <div class="field">
        <label>Severity</label>
        <select bind:value={newRule.severity}>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
      </div>
      {#if newRule.entity_type === 'account'}
        <div class="field">
          <label>Condition Field</label>
          <input type="text" bind:value={newRule.condition_field} placeholder="state" />
        </div>
      {:else}
        <div class="field">
          <label>Metric Name</label>
          <input type="text" bind:value={newRule.metric_name} placeholder="pipeline:consume:consumer_lag" />
        </div>
      {/if}
      <div class="field">
        <label>Operator</label>
        <select bind:value={newRule.condition_op}>
          <option value="==">== (equals)</option>
          <option value="!=">!= (not equals)</option>
          <option value="in">in (comma-separated)</option>
          <option value="contains">contains</option>
          <option value=">">&gt; (greater)</option>
          <option value="<">&lt; (less)</option>
        </select>
      </div>
      <div class="field">
        <label>Value</label>
        <input type="text" bind:value={newRule.condition_value} placeholder="error,recovering" />
      </div>
      <div class="field">
        <label>Cooldown (sec)</label>
        <input type="number" bind:value={newRule.cooldown_seconds} />
      </div>
      <div class="field">
        <label>FOR duration (sec)</label>
        <input type="number" bind:value={newRule.for_seconds} />
      </div>
      <div class="field full">
        <label>Message Template</label>
        <input type="text" bind:value={newRule.message_template} placeholder="Alert: {entity_id} - {state}" />
      </div>
    </div>
    <button class="btn btn-primary" onclick={createRule}>Create Rule</button>
  </div>
{/if}

<!-- Rules list -->
{#if loading}
  <div class="loading">Loading rules...</div>
{:else}
  <div class="rules-list">
    {#each rules as rule (rule.name)}
      <div class="rule-card" class:disabled={!rule.enabled}>
        <div class="rule-header">
          <div class="rule-title">
            <span class="rule-name">{rule.name}</span>
            <span class="badge" class:badge-red={rule.severity === 'critical'} class:badge-yellow={rule.severity === 'warning'}>
              {rule.severity}
            </span>
            <span class="badge" class:badge-green={rule.entity_type === 'account'} class:badge-gray={rule.entity_type === 'metric'}>
              {rule.entity_type}
            </span>
          </div>
          <div class="rule-actions">
            <label class="toggle">
              <input type="checkbox" checked={rule.enabled}
                onchange={(e) => toggleRule(rule.name, e.currentTarget.checked)} />
              <span class="toggle-slider"></span>
            </label>
            <button class="btn btn-small" onclick={() => deleteRule(rule.name)}>Delete</button>
          </div>
        </div>
        {#if rule.description}
          <div class="rule-desc">{rule.description}</div>
        {/if}
        <div class="rule-condition">
          {#if rule.entity_type === 'metric' && rule.metric_name}
            <code>{rule.metric_name} [{rule.metric_window}] {rule.condition_op} {rule.condition_value}</code>
          {:else}
            <code>{rule.condition_field} {rule.condition_op} {rule.condition_value}</code>
          {/if}
          {#if rule.for_seconds > 0}
            <span class="for-badge">FOR {rule.for_seconds}s</span>
          {/if}
          {#if rule.cooldown_seconds > 0}
            <span class="cooldown-badge">cooldown: {rule.cooldown_seconds}s</span>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .back-link {
    font-size: 0.82em;
    color: var(--text-muted);
    text-decoration: none;
  }
  .back-link:hover { color: var(--accent); }
  .loading {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
  }
  .btn-primary {
    background: rgba(137, 180, 250, 0.12);
    border-color: var(--accent);
    color: var(--accent);
  }
  .btn-primary:hover {
    background: rgba(137, 180, 250, 0.2);
  }
  .btn-small {
    padding: 3px 10px;
    font-size: 0.78em;
    color: var(--red);
    border-color: var(--red);
  }
  .btn-small:hover { background: rgba(239, 68, 68, 0.1); }

  /* Create form */
  .create-form {
    padding: 20px;
  }
  .create-form h3 {
    margin-bottom: 14px;
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 14px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field.full { grid-column: span 2; }
  .field label {
    font-size: 0.75em;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .field input, .field select {
    padding: 6px 10px;
    background: var(--bg-overlay);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 0.88em;
    font-family: inherit;
  }
  .field input:focus, .field select:focus {
    outline: none;
    border-color: var(--accent);
  }

  /* Rules list */
  .rules-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .rule-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    transition: opacity 0.2s;
  }
  .rule-card.disabled {
    opacity: 0.5;
  }
  .rule-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .rule-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rule-name {
    font-weight: 600;
    font-size: 0.92em;
    font-family: 'JetBrains Mono', monospace;
  }
  .rule-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rule-desc {
    font-size: 0.82em;
    color: var(--text-secondary);
    margin-bottom: 6px;
  }
  .rule-condition {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .rule-condition code {
    background: var(--bg-overlay);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.8em;
    color: var(--accent);
  }
  .for-badge, .cooldown-badge {
    font-size: 0.72em;
    padding: 2px 6px;
    border-radius: 8px;
    background: rgba(249, 226, 175, 0.1);
    color: #f9e2af;
  }
  .cooldown-badge {
    background: rgba(166, 173, 200, 0.1);
    color: var(--text-muted);
  }

  /* Toggle switch */
  .toggle {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 20px;
  }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle-slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background-color: #45475a;
    border-radius: 20px;
    transition: 0.2s;
  }
  .toggle-slider::before {
    content: "";
    position: absolute;
    height: 14px;
    width: 14px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    border-radius: 50%;
    transition: 0.2s;
  }
  .toggle input:checked + .toggle-slider {
    background-color: #22c55e;
  }
  .toggle input:checked + .toggle-slider::before {
    transform: translateX(16px);
  }
</style>

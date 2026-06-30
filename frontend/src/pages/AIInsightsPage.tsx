import { useWeeklyMemo, useGenerateWeeklyMemo, useAISettings } from '../hooks/useNewApis';
import toast from 'react-hot-toast';

export default function AIInsightsPage() {
  const { data: memo, isLoading: loadingMemo } = useWeeklyMemo();
  const { data: settings } = useAISettings();
  const generateMemo = useGenerateWeeklyMemo();

  const handleGenerate = () => {
    generateMemo.mutate(undefined, {
      onSuccess: () => toast.success('Weekly memo generated'),
      onError: () => toast.error('Failed to generate memo'),
    });
  };

  return (
    <div className="page">
      <h1>AI Insights</h1>
      <p>
        AI-generated portfolio analysis and recommendations.
        {settings && (
          <span style={{ marginLeft: '8px', fontSize: '12px', opacity: 0.6 }}>
            Mode: {settings.ai_provider} | {settings.is_enabled ? 'Enabled' : 'Disabled'}
          </span>
        )}
      </p>

      {/* Weekly Memo */}
      <div style={{ marginTop: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{ margin: 0 }}>Weekly Portfolio Memo</h2>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generateMemo.isPending}
            style={{ padding: '6px 14px', borderRadius: '8px', background: '#3B82F6', color: 'white', border: 'none', fontSize: '13px', cursor: 'pointer' }}
          >
            {generateMemo.isPending ? 'Generating...' : 'Regenerate'}
          </button>
        </div>

        {loadingMemo ? (
          <p>Loading memo...</p>
        ) : memo ? (
          <div style={{ marginTop: '16px' }}>
            {/* Generation metadata */}
            <div style={{ fontSize: '12px', opacity: 0.6, marginBottom: '12px' }}>
              Generated: {new Date(memo.generated_at).toLocaleString()} | Mode: {memo.generation_mode}
            </div>

            {/* Stale warnings */}
            {memo.stale_warnings && memo.stale_warnings.length > 0 && (
              <div style={{ padding: '8px 12px', background: 'rgba(245,158,11,0.1)', borderRadius: '8px', border: '1px solid #F59E0B', marginBottom: '12px', fontSize: '13px' }}>
                ⚠️ {memo.stale_warnings.join(', ')}
              </div>
            )}

            {/* Memo content (rendered as markdown-like text) */}
            <div style={{
              padding: '20px',
              borderRadius: '12px',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              whiteSpace: 'pre-wrap',
              fontFamily: 'inherit',
              fontSize: '14px',
              lineHeight: '1.7',
            }}>
              {memo.content}
            </div>
          </div>
        ) : (
          <p style={{ marginTop: '16px', opacity: 0.6 }}>No memo available. Click &quot;Regenerate&quot; to create one.</p>
        )}
      </div>

      {/* Disclaimer */}
      <div style={{ marginTop: '32px', fontSize: '12px', opacity: 0.5, fontStyle: 'italic' }}>
        AI insights are analytical observations, not investment advice. They may be based on incomplete data.
      </div>
    </div>
  );
}

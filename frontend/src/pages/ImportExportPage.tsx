import { useState } from 'react';
import { usePreviewImport, useImportTransactions } from '../hooks/useNewApis';
import { importExportApi } from '../api';
import toast from 'react-hot-toast';

export default function ImportExportPage() {
  const [file, setFile] = useState<File | null>(null);
  const previewMutation = usePreviewImport();
  const importMutation = useImportTransactions();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    previewMutation.reset();
    importMutation.reset();
  };

  const handlePreview = () => {
    if (!file) return;
    previewMutation.mutate(file);
  };

  const handleImport = () => {
    if (!file) return;
    importMutation.mutate(file, {
      onSuccess: (data) => {
        toast.success(`Successfully imported ${data.imported_count} transactions`);
        setFile(null);
        previewMutation.reset();
      },
      onError: () => toast.error('Import failed'),
    });
  };

  const handleExportCsv = async () => {
    try {
      const blob = await importExportApi.exportTransactionsCsv();
      downloadBlob(blob, 'transactions.csv');
      toast.success('CSV exported');
    } catch {
      toast.error('Export failed');
    }
  };

  const handleExportBackup = async () => {
    try {
      const blob = await importExportApi.exportFullBackup();
      downloadBlob(blob, 'investment_backup.json');
      toast.success('Backup exported');
    } catch {
      toast.error('Export failed');
    }
  };

  const preview = previewMutation.data;

  return (
    <div className="page">
      <h1>Import / Export</h1>
      <p>Import transactions from CSV or export your full portfolio data.</p>

      {/* Import Section */}
      <div style={{ marginTop: '24px' }}>
        <h2>Import Transactions (CSV)</h2>
        <p style={{ fontSize: '13px', opacity: 0.7 }}>
          Required columns: date, stock_symbol, action, quantity, price_per_share, broker.
          Optional: brokerage_fee, vat.
        </p>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '12px' }}>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            aria-label="Select CSV file"
          />
          <button
            type="button"
            onClick={handlePreview}
            disabled={!file || previewMutation.isPending}
            style={{ padding: '8px 16px', borderRadius: '8px', background: '#3B82F6', color: 'white', border: 'none', cursor: 'pointer' }}
          >
            {previewMutation.isPending ? 'Validating...' : 'Preview'}
          </button>
        </div>

        {/* Preview Results */}
        {preview && (
          <div style={{ marginTop: '16px' }}>
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: preview.valid ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${preview.valid ? '#22C55E' : '#EF4444'}`,
            }}>
              <strong>{preview.valid ? '✅ Validation passed' : '❌ Validation failed'}</strong>
              <span style={{ marginLeft: '12px' }}>{preview.row_count} rows</span>
            </div>

            {preview.errors.length > 0 && (
              <div style={{ marginTop: '12px', maxHeight: '200px', overflow: 'auto' }}>
                {preview.errors.map((err: { row: number; field: string | null; message: string }, i: number) => (
                  <div key={i} style={{ fontSize: '13px', padding: '4px 0', color: '#EF4444' }}>
                    Row {err.row}{err.field ? ` [${err.field}]` : ''}: {err.message}
                  </div>
                ))}
              </div>
            )}

            {preview.valid && (
              <button
                type="button"
                onClick={handleImport}
                disabled={importMutation.isPending}
                style={{ marginTop: '12px', padding: '10px 20px', borderRadius: '8px', background: '#22C55E', color: 'white', border: 'none', fontWeight: 600, cursor: 'pointer' }}
              >
                {importMutation.isPending ? 'Importing...' : `Import ${preview.row_count} Transactions`}
              </button>
            )}
          </div>
        )}

        {importMutation.isSuccess && (
          <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(34,197,94,0.1)', borderRadius: '8px', border: '1px solid #22C55E' }}>
            ✅ Imported {importMutation.data.imported_count} transactions successfully.
          </div>
        )}
      </div>

      {/* Export Section */}
      <div style={{ marginTop: '40px' }}>
        <h2>Export Data</h2>
        <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
          <button
            type="button"
            onClick={handleExportCsv}
            style={{ padding: '10px 20px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg)', cursor: 'pointer', fontWeight: 500 }}
          >
            📄 Export Transactions (CSV)
          </button>
          <button
            type="button"
            onClick={handleExportBackup}
            style={{ padding: '10px 20px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg)', cursor: 'pointer', fontWeight: 500 }}
          >
            💾 Full Account Backup (JSON)
          </button>
        </div>
      </div>
    </div>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

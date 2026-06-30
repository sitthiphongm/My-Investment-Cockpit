/**
 * React Query hooks for the new v2 API endpoints:
 * behavioral analytics, AI insights, simulator, import/export, position sizing, cash ledger.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  behavioralApi,
  aiInsightsApi,
  simulatorApi,
  importExportApi,
  positionSizingApi,
  cashLedgerApi,
} from '../api';

// ===== Behavioral Analytics =====

export function useBehavioralStats() {
  return useQuery({
    queryKey: ['behavioral', 'stats'],
    queryFn: behavioralApi.getStats,
  });
}

export function useBehavioralPatterns() {
  return useQuery({
    queryKey: ['behavioral', 'patterns'],
    queryFn: behavioralApi.getPatterns,
  });
}

// ===== AI Insights =====

export function useWeeklyMemo() {
  return useQuery({
    queryKey: ['ai', 'weekly-memo'],
    queryFn: aiInsightsApi.getWeeklyMemo,
  });
}

export function useGenerateWeeklyMemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: aiInsightsApi.generateWeeklyMemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai', 'weekly-memo'] });
    },
  });
}

export function useTradeReview(transactionId: string) {
  return useQuery({
    queryKey: ['ai', 'trade-review', transactionId],
    queryFn: () => aiInsightsApi.getTradeReview(transactionId),
    enabled: !!transactionId,
  });
}

export function useAISettings() {
  return useQuery({
    queryKey: ['ai', 'settings'],
    queryFn: aiInsightsApi.getSettings,
  });
}

// ===== Scenario Simulator =====

export function useRunSimulation() {
  return useMutation({
    mutationFn: simulatorApi.run,
  });
}

// ===== Import/Export =====

export function usePreviewImport() {
  return useMutation({
    mutationFn: importExportApi.previewImport,
  });
}

export function useImportTransactions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importExportApi.importTransactions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ===== Position Sizing =====

export function usePositionSizing() {
  return useMutation({
    mutationFn: positionSizingApi.calculate,
  });
}

// ===== Cash Ledger =====

export function useCashLedger() {
  return useQuery({
    queryKey: ['cash-ledger'],
    queryFn: cashLedgerApi.get,
  });
}

export function useCashLedgerSummary() {
  return useQuery({
    queryKey: ['cash-ledger', 'summary'],
    queryFn: cashLedgerApi.getSummary,
  });
}

export function useCreateCashAdjustment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cashLedgerApi.createAdjustment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cash-ledger'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

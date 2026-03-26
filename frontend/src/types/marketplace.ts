export interface MarketplaceProvider {
  id: string;
  name: string;
  description: string | null;
  asset_class: "forex" | "crypto" | "both";
  is_active: boolean;
  win_rate: number | null;
  total_pnl_pips: number | null;
  max_drawdown_pips: number | null;
  signal_count: number;
  subscriber_count: number;
  track_record_days: number;
  stats_last_computed_at: string | null;
  created_at?: string;
  /** Admin-only field — present in admin responses */
  telegram_channel_id?: string;
}

export interface MarketplaceSubscription {
  id: string;
  provider_id: string;
  provider: MarketplaceProvider;
  is_active: boolean;
  created_at: string;
}

export type MarketplaceSort = "win_rate" | "signals" | "subscribers";
export type MarketplaceFilter = "all" | "forex" | "crypto";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserMe;
  email_sent?: boolean;
}

export interface UserMe {
  id: string;
  email: string;
  subscription_tier: string;
  is_admin: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface TelegramStatusResponse {
  connected: boolean;
  phone_number: string | null;
  connected_at: string | null;
  disconnected_at: string | null;
  disconnected_reason: string | null;
  last_signal_at: string | null;
}

export interface SendCodeResponse {
  phone_code_hash: string;
}

export interface VerifyCodeResponse {
  status: string;
  requires_2fa: boolean;
}

export interface ChannelInfo {
  id: string;
  title: string;
  username: string | null;
}

export type DestinationType = "sagemaster_forex" | "sagemaster_crypto" | "custom";

export interface RoutingRuleCreate {
  source_channel_id: string;
  source_channel_name?: string;
  destination_webhook_url: string;
  payload_version: "V1" | "V2";
  symbol_mappings: Record<string, string>;
  risk_overrides: Record<string, unknown>;
  webhook_body_template?: Record<string, unknown> | null;
  rule_name?: string | null;
  destination_label?: string | null;
  destination_type?: DestinationType;
  custom_ai_instructions?: string | null;
  enabled_actions?: string[] | null;
  keyword_blacklist?: string[];
}

export interface RoutingRuleUpdate {
  source_channel_name?: string;
  destination_webhook_url?: string;
  payload_version?: "V1" | "V2";
  symbol_mappings?: Record<string, string>;
  risk_overrides?: Record<string, unknown>;
  webhook_body_template?: Record<string, unknown> | null;
  rule_name?: string | null;
  destination_label?: string | null;
  destination_type?: DestinationType;
  custom_ai_instructions?: string | null;
  enabled_actions?: string[] | null;
  keyword_blacklist?: string[];
  is_active?: boolean;
}

export interface RoutingRuleResponse {
  id: string;
  user_id: string;
  source_channel_id: string;
  source_channel_name: string | null;
  destination_webhook_url: string;
  payload_version: string;
  symbol_mappings: Record<string, string>;
  risk_overrides: Record<string, unknown>;
  webhook_body_template: Record<string, unknown> | null;
  rule_name: string | null;
  destination_label: string | null;
  destination_type: DestinationType;
  custom_ai_instructions: string | null;
  enabled_actions: string[] | null;
  keyword_blacklist: string[];
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface NotificationPreferences {
  email_on_success: boolean;
  email_on_failure: boolean;
  email_on_disconnect: boolean;
  telegram_on_success: boolean;
  telegram_on_failure: boolean;
  telegram_bot_chat_id: number | null;
}

export interface TelegramBotLinkResponse {
  bot_link: string;
}

export interface KeywordBlacklistUpdate {
  keyword_blacklist: string[];
}

export interface SignalLogResponse {
  id: string;
  user_id: string;
  routing_rule_id: string | null;
  raw_message: string;
  parsed_data: Record<string, unknown> | null;
  webhook_payload: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  processed_at: string;
  message_id: number | null;
  channel_id: string | null;
  reply_to_msg_id: number | null;
}

export interface PaginatedLogs {
  total: number;
  limit: number;
  offset: number;
  items: SignalLogResponse[];
}

export interface LogStatsResponse {
  total: number;
  success: number;
  failed: number;
  ignored: number;
}

export interface TestWebhookResponse {
  success: boolean;
  status_code: number | null;
  error: string | null;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

// Admin types

export interface AdminUserSummary {
  id: string;
  email: string;
  subscription_tier: string;
  is_admin: boolean;
  is_disabled: boolean;
  created_at: string;
  rule_count: number;
  signal_count: number;
  telegram_connected: boolean;
}

export interface PaginatedAdminUsers {
  total: number;
  limit: number;
  offset: number;
  items: AdminUserSummary[];
}

export interface AdminRoutingRule {
  id: string;
  source_channel_id: string;
  source_channel_name: string | null;
  destination_webhook_url: string;
  payload_version: string;
  rule_name: string | null;
  destination_type: string;
  is_active: boolean;
}

export interface AdminSignalLog extends SignalLogResponse {
  user_email: string;
}

export interface AdminUserDetail extends AdminUserSummary {
  routing_rules: AdminRoutingRule[];
  recent_signals: AdminSignalLog[];
  notification_preferences: Record<string, unknown>;
}

export interface PaginatedAdminSignals {
  total: number;
  limit: number;
  offset: number;
  items: AdminSignalLog[];
}

export interface AdminSignalStats {
  total_today: number;
  success_rate_24h: number;
  top_failing_channels: { channel_id: string; fail_count: number }[];
}

export interface AdminHealthStats {
  total_users: number;
  active_users_7d: number;
  signals_today: number;
  signals_this_week: number;
  success_rate_24h: number;
  active_routing_rules: number;
  active_telegram_sessions: number;
}

// Parser Manager types

export interface ParserConfigResponse {
  id: string;
  config_key: string;
  system_prompt: string | null;
  model_name: string | null;
  temperature: number | null;
  version: number;
  is_active: boolean;
  change_note: string | null;
  changed_by_email: string | null;
  created_at: string;
}

export interface PaginatedParserHistory {
  total: number;
  limit: number;
  offset: number;
  items: ParserConfigResponse[];
}

export interface TestParseRequest {
  raw_message: string;
  custom_instructions?: string | null;
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  message: string;
}

export interface TestParseResponse {
  parsed: Record<string, unknown>;
  model_used: string;
  temperature_used: number;
  validation_checks: ValidationCheck[];
  webhook_payload: Record<string, unknown> | null;
}

export interface ReplayResponse {
  original_parsed: Record<string, unknown> | null;
  new_parsed: Record<string, unknown>;
  model_used: string;
  temperature_used: number;
  validation_checks: ValidationCheck[];
  raw_message: string;
}

export interface TestDispatchRequest {
  raw_message: string;
  routing_rule_id: string;
  custom_instructions?: string | null;
}

export interface TestDispatchResponse {
  status_code: number;
  response_body: string;
}

// Global Settings
export interface GlobalSetting {
  key: string;
  value: string;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

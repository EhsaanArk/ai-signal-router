export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserMe {
  id: string;
  email: string;
  subscription_tier: string;
  created_at: string;
}

export interface TelegramStatusResponse {
  connected: boolean;
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

export interface RoutingRuleCreate {
  source_channel_id: string;
  source_channel_name?: string;
  destination_webhook_url: string;
  payload_version: "V1" | "V2";
  symbol_mappings: Record<string, string>;
  risk_overrides: Record<string, unknown>;
}

export interface RoutingRuleUpdate {
  source_channel_name?: string;
  destination_webhook_url?: string;
  payload_version?: "V1" | "V2";
  symbol_mappings?: Record<string, string>;
  risk_overrides?: Record<string, unknown>;
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
  is_active: boolean;
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
}

export interface PaginatedLogs {
  total: number;
  limit: number;
  offset: number;
  items: SignalLogResponse[];
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

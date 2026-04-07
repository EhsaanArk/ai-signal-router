import { useNavigate } from "react-router-dom";
import { Bot, ExternalLink, MessageCircle, Radio, Wifi, WifiOff } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTelegramStatus } from "@/hooks/use-telegram";
import { useBotLinking } from "@/hooks/use-bot-linking";
import { usePageTitle } from "@/hooks/use-page-title";

function maskPhone(phone: string | null): string {
  if (!phone) return "Unknown";
  if (phone.length <= 4) return phone;
  return phone.slice(0, -4).replace(/./g, "*") + phone.slice(-4);
}

function BotCard() {
  const { state, isLinked, isLoading, justLinked, connect, cancel, chatId } = useBotLinking();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 space-y-4">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-8 w-40" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden border-primary/30 bg-primary/[0.02] dark:bg-primary/[0.04]">
      {/* Recommended indicator */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary" />
      <CardHeader className="pb-2 pt-5 px-5">
        <div className="flex items-center justify-between">
          <Bot className="h-7 w-7 text-primary" />
          <span className="text-[9px] font-semibold bg-primary/10 text-primary px-2 py-0.5 rounded-full uppercase tracking-wider">
            Recommended
          </span>
        </div>
        <CardTitle className="text-sm font-semibold mt-3">Telegram Bot</CardTitle>
        <p className="text-[11px] text-muted-foreground">Vibe trade from Telegram</p>
      </CardHeader>
      <CardContent className="px-5 pb-5 space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Message the bot with your trade idea. Sage Intelligence parses it, shows a preview, and routes to your broker on confirm.
        </p>

        <ul className="space-y-1.5">
          {[
            'Natural language — "buy gold long SL 2340"',
            "AI confirmation before every dispatch",
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-[11px] text-muted-foreground">
              <span className="text-primary mt-0.5 text-xs">+</span>
              {item}
            </li>
          ))}
        </ul>

        {/* Status + Action */}
        {isLinked ? (
          <div className="space-y-2 pt-1">
            {justLinked && (
              <div className="flex items-center gap-2 rounded-md border border-green-500/20 bg-green-500/5 p-2.5">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <p className="text-[11px] text-green-600 dark:text-green-400">
                  Telegram bot linked! You can now send trade signals.
                </p>
              </div>
            )}
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-[11px] text-green-600 dark:text-green-400">Connected</span>
              {chatId && (
                <span className="text-[10px] text-muted-foreground ml-1">
                  Chat ID: {String(chatId).slice(-6)}
                </span>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground">
              Manage notifications in <a href="/settings" className="underline">Settings</a>.
            </p>
          </div>
        ) : state === "waiting" ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 p-2.5">
              <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              <p className="text-[11px] text-primary">
                Waiting for you to press <strong>START</strong> in Telegram...
              </p>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Open the bot and press START. This page updates automatically.
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-[10px] text-muted-foreground"
              onClick={cancel}
            >
              Cancel
            </Button>
          </div>
        ) : state === "timedOut" ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 p-2.5">
              <div className="h-2 w-2 rounded-full bg-amber-500" />
              <p className="text-[11px] text-amber-600 dark:text-amber-400">
                Link timed out. Please try again.
              </p>
            </div>
            <Button variant="outline" size="sm" className="h-7 text-xs" onClick={connect}>
              Retry
            </Button>
          </div>
        ) : state === "error" ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/5 p-2.5">
              <div className="h-2 w-2 rounded-full bg-red-500" />
              <p className="text-[11px] text-red-600 dark:text-red-400">
                Failed to generate link. Please try again.
              </p>
            </div>
            <Button variant="outline" size="sm" className="h-7 text-xs" onClick={connect}>
              Retry
            </Button>
          </div>
        ) : (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-zinc-500" />
              <span className="text-[11px] text-muted-foreground">Not connected</span>
            </div>
            <Button
              size="sm"
              className="h-8 text-xs"
              onClick={connect}
            >
              <MessageCircle className="mr-1.5 h-3 w-3" />
              Connect Telegram Bot
              <ExternalLink className="ml-1.5 h-2.5 w-2.5" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MtprotoCard() {
  const navigate = useNavigate();
  const { data: status, isLoading, isError } = useTelegramStatus();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 space-y-4">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-8 w-40" />
        </CardContent>
      </Card>
    );
  }

  const isConnected = status?.connected ?? false;

  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="pb-2 pt-5 px-5">
        <div className="flex items-center justify-between">
          <Radio className="h-7 w-7 text-muted-foreground" />
          <span className="text-[9px] font-semibold bg-muted text-muted-foreground px-2 py-0.5 rounded-full uppercase tracking-wider">
            Advanced
          </span>
        </div>
        <CardTitle className="text-sm font-semibold mt-3">Direct Telegram</CardTitle>
        <p className="text-[11px] text-muted-foreground">Auto-copy signals from channels</p>
      </CardHeader>
      <CardContent className="px-5 pb-5 space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Connect your Telegram account to monitor signal channels. Signals are parsed and routed to your broker automatically.
        </p>

        <ul className="space-y-1.5">
          {[
            "Monitor unlimited channels, multi-destination routing",
            "Requires Telegram phone number verification",
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-[11px] text-muted-foreground">
              <span className="text-muted-foreground/60 mt-0.5 text-xs">+</span>
              {item}
            </li>
          ))}
        </ul>

        {/* Status + Action */}
        {isError ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="text-[11px] text-amber-600 dark:text-amber-400">Status unavailable</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => navigate("/telegram")}
            >
              Manage Connection
            </Button>
          </div>
        ) : isConnected ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <Wifi className="h-3 w-3 text-green-500" />
              <span className="text-[11px] text-green-600 dark:text-green-400">Connected</span>
              {status?.phone_number && (
                <span className="text-[10px] text-muted-foreground ml-1">
                  {maskPhone(status.phone_number)}
                </span>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => navigate("/telegram")}
            >
              Manage →
            </Button>
          </div>
        ) : (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <WifiOff className="h-3 w-3 text-zinc-500" />
              <span className="text-[11px] text-muted-foreground">Not connected</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => navigate("/telegram")}
            >
              Connect Telegram Account →
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ConnectorsPage() {
  usePageTitle("Connectors");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Connectors</h1>
        <p className="text-sm text-muted-foreground">
          Two ways to trade — pick one or use both
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
        <BotCard />
        <MtprotoCard />
      </div>
    </div>
  );
}

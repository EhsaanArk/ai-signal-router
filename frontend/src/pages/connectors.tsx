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
          <Skeleton className="h-10 w-10 rounded-lg" />
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-8 w-40" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="pb-2 pt-5 px-5">
        <div className="flex items-center justify-between">
          <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Bot className="h-5 w-5 text-blue-500" />
          </div>
          <span className="text-[9px] font-semibold bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded-full uppercase tracking-wider">
            New
          </span>
        </div>
        <CardTitle className="text-sm font-semibold mt-3">Telegram Bot</CardTitle>
        <p className="text-[11px] text-muted-foreground">Vibe Trading</p>
      </CardHeader>
      <CardContent className="px-5 pb-5 space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Send your own trade ideas as messages to our Telegram bot. Sage Intelligence parses your intent, shows a preview, and routes to your broker on confirm.
        </p>

        <ul className="space-y-1.5">
          {[
            'Natural language — "buy gold long SL 2340"',
            "AI-powered confirmation before dispatch",
            "No Telegram account connection needed",
            "Works from any Telegram client",
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-[11px] text-muted-foreground">
              <span className="text-green-500 mt-0.5">✓</span>
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
              Manage notification preferences in <a href="/settings" className="underline">Settings</a>.
            </p>
          </div>
        ) : state === "waiting" ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2 rounded-md border border-blue-500/20 bg-blue-500/5 p-2.5">
              <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
              <p className="text-[11px] text-blue-600 dark:text-blue-400">
                Waiting for you to press <strong>START</strong> in Telegram...
              </p>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Open the Telegram bot that just opened and press START. This page will update automatically.
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
              <Bot className="mr-1.5 h-3 w-3" />
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
              <Bot className="mr-1.5 h-3 w-3" />
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
              variant="default"
              size="sm"
              className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700"
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
          <Skeleton className="h-10 w-10 rounded-lg" />
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
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
          <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <Radio className="h-5 w-5 text-emerald-500" />
          </div>
          <span className="text-[9px] font-semibold bg-zinc-500/10 text-zinc-400 px-2 py-0.5 rounded-full uppercase tracking-wider">
            Signal Copying
          </span>
        </div>
        <CardTitle className="text-sm font-semibold mt-3">Direct Telegram</CardTitle>
        <p className="text-[11px] text-muted-foreground">Auto-Copy from Channels</p>
      </CardHeader>
      <CardContent className="px-5 pb-5 space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Connect your personal Telegram account to monitor signal channels. Signals are automatically parsed and routed to your broker in real-time.
        </p>

        <ul className="space-y-1.5">
          {[
            "Monitor unlimited Telegram channels",
            "Automatic signal detection and parsing",
            "Multi-destination routing with symbol mapping",
            "Requires phone number verification",
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-[11px] text-muted-foreground">
              <span className="text-green-500 mt-0.5">✓</span>
              {item}
            </li>
          ))}
        </ul>

        {/* Status + Action */}
        {isError ? (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="text-[11px] text-amber-600 dark:text-amber-400">Connection status unavailable</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={() => navigate("/telegram")}
            >
              <Radio className="mr-1.5 h-3 w-3" />
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
              <Radio className="mr-1.5 h-3 w-3" />
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
          Choose how you want to trade with Sage Radar AI
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
        <BotCard />
        <MtprotoCard />
      </div>
    </div>
  );
}

# Trading journal — build spec (v1)

## What this is
A simple, multi-user manual trade journal. Each trader signs up, logs every trade by hand, and sees their track record and analysis (RR, win rate, R-multiples, drawdown). Keep this version minimal — no auto-import, no social features, no broker integrations.

## Stack
- Next.js (App Router, TypeScript, Tailwind CSS)
- Supabase: Postgres + Auth (email/password)
- Recharts for the equity curve chart
- Deploy: Vercel (frontend) + Supabase (backend)

## Database schema

```sql
create table profiles (
  id uuid primary key references auth.users(id),
  email text,
  display_name text,
  starting_balance numeric default 0,
  created_at timestamptz default now()
);

create table trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) not null,
  pair text not null,
  direction text check (direction in ('long','short')) not null,
  trade_date date not null,
  trade_time time,
  entry_price numeric not null,
  stop_loss_price numeric not null,
  take_profit_price numeric,
  exit_price numeric,
  risk_percent numeric,
  risk_amount numeric,
  planned_rr numeric,
  result text check (result in ('TP','SL','BE','Partial','Open')) default 'Open',
  profit_loss_usd numeric,
  profit_loss_r numeric,
  notes text,
  screenshot_url text,
  created_at timestamptz default now()
);

alter table profiles enable row level security;
create policy "own profile only" on profiles
  for all using (auth.uid() = id);

alter table trades enable row level security;
create policy "own trades only" on trades
  for all using (auth.uid() = user_id);
```

## Pages

### 1. `/login` and `/signup`
Supabase email/password auth. On signup, create a `profiles` row and ask the user to enter their starting account balance once (`starting_balance`).

### 2. `/dashboard` (home after login)
- Top row: stat cards — Win rate, Total trades, Total R, Current balance, Avg RR
- Below: equity curve line chart (balance over time, computed from trades ordered by date)
- Below that: last 5–10 trades in a compact table, with a link to the full journal

### 3. `/trades` (the journal)
Full table of all trades: date, pair, direction, RR, result, R-multiple, $ P/L. Sortable by any column. Filter dropdowns for pair, month, result. "Add trade" button opens the entry form.

### 4. Trade entry form (modal or `/trades/new`)
Fields, in this order:
- Pair (text input or dropdown of common pairs)
- Direction (long/short toggle)
- Date, time
- Entry price, stop loss price, take profit price → RR auto-calculates and displays live as the user types
- Risk % and risk $ (one auto-fills from the other using the current account balance)
- Result — dropdown: TP / SL / BE / Partial / Open
- Exit price (shown once result ≠ Open)
- Notes (text area)
- Screenshot URL (paste a TradingView link, same as the current sheet)

On save: compute `profit_loss_usd` and `profit_loss_r` from entry/exit/risk and store them alongside the raw inputs.

### 5. `/trades/[id]` (trade detail)
Read-only view of every field above, with edit and delete actions. Show a screenshot preview if the URL is an image link.

## Core calculations
- **Planned RR** = reward ÷ risk, from entry/stop-loss/take-profit prices
- **Realized R** = profit_loss_usd ÷ risk_amount
- **Win rate** = (TP + Partial results) ÷ total closed trades
- **Expectancy** = average profit_loss_r across all closed trades
- **Profit factor** = gross profit ÷ gross loss
- **Running balance** = starting_balance + cumulative profit_loss_usd, ordered by date
- **Max drawdown** = largest peak-to-trough drop in running balance

## Explicitly out of scope for v1
- Multiple trading accounts per user
- CSV import
- File upload for screenshots (URL only, matching the current sheet)
- Public or shareable profiles
- Broker API auto-import
- Leaderboards or any social features

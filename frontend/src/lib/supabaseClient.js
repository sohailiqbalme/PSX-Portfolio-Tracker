/**
 * src/lib/supabaseClient.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Initialises and exports a singleton Supabase JS client.
 *
 * Environment variables (set in frontend/.env):
 *   VITE_SUPABASE_URL      — https://<project-ref>.supabase.co
 *   VITE_SUPABASE_ANON_KEY — Public anon key (safe to expose in the browser)
 *
 * Usage:
 *   import supabase from '@/lib/supabaseClient'
 *   const { data, error } = await supabase.auth.signInWithPassword({ ... })
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL
const supabaseAnon = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnon) {
  console.error(
    '[PSX] Missing Supabase env vars.\n' +
    'Create frontend/.env with:\n' +
    '  VITE_SUPABASE_URL=https://<project>.supabase.co\n' +
    '  VITE_SUPABASE_ANON_KEY=<your-anon-key>'
  )
}

const supabase = createClient(supabaseUrl, supabaseAnon, {
  auth: {
    // Persist session in localStorage so the user stays logged in on refresh
    persistSession:    true,
    autoRefreshToken:  true,
    detectSessionInUrl: true,
  },
})

export default supabase

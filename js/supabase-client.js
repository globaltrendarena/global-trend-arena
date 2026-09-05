// Shared Supabase client bootstrap.
// Load this AFTER the Supabase JS CDN script in any page that needs it:
//   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
//   <script src="js/supabase-client.js"></script>
//
// Other scripts should do:
//   await window.sbReady;
//   if (window.sbConfigured) { const { data, error } = await window.sb.from('products').select('*'); }

window.sbReady = (async function initSupabase() {
  try {
    const res = await fetch('config.json');
    const config = await res.json();
    const { url, anonKey } = config.supabase || {};

    if (!url || !anonKey || url.includes('YOUR_') || anonKey.includes('YOUR_')) {
      console.warn('[supabase-client] Not configured yet — add supabase.url / supabase.anonKey to config.json.');
      window.sb = null;
      window.sbConfigured = false;
      return null;
    }

    window.sb = supabase.createClient(url, anonKey);
    window.sbConfigured = true;
    return window.sb;
  } catch (err) {
    console.error('[supabase-client] Failed to initialize:', err);
    window.sb = null;
    window.sbConfigured = false;
    return null;
  }
})();

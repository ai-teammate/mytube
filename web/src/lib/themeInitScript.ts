/**
 * Blocking inline script that reads the user's theme preference from
 * localStorage and applies it to <body> before first paint, preventing
 * a flash of unstyled content (FOUC) when dark mode is active.
 *
 * Exported as a separate module so it can be independently tested
 * without importing the full layout module.
 */
export const themeInitScript = `(function(){try{var t=localStorage.getItem('theme');if(t==='dark')document.body.setAttribute('data-theme','dark')}catch(e){}})()`;

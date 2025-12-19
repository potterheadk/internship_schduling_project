/* static/js/translation.js */

// --- HELPER FUNCTIONS (Define first so they can be used in IIFE) ---

function setCookie(key, value) {
    const date = new Date();
    date.setTime(date.getTime() + (30 * 24 * 60 * 60 * 1000)); // 30 Days
    const expires = "expires=" + date.toUTCString();

    // Set cookie on Root Path so it applies everywhere
    document.cookie = key + "=" + value + "; " + expires + "; path=/";

    // Safety: Set on domain too (helps with localhost issues)
    document.cookie = key + "=" + value + "; " + expires + "; path=/; domain=" + window.location.hostname;
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function applyStoredLanguage() {
    const storedLang = getCookie('googtrans');

    if (storedLang === '/en/es') {
        // Apply Spanish translation
        const selectElement = document.querySelector('.goog-te-combo');
        if (selectElement) {
            selectElement.value = 'es';
            selectElement.dispatchEvent(new Event('change'));
        }
    }
    // If '/en/en' or null, keep default English (no action needed)
}

function updateButtonState() {
    const toggleBtn = document.getElementById('langToggle');
    if (!toggleBtn) return;

    const cookie = getCookie('googtrans');

    // Update Button UI based on cookie
    if (cookie === '/en/es') {
        // State is Spanish
        toggleBtn.innerHTML = `🇪🇸 ES`;
        toggleBtn.style.color = "#4c7dff";
        toggleBtn.style.borderColor = "#4c7dff";
    } else {
        // State is English (or default)
        toggleBtn.innerHTML = `🇺🇸 EN`;
        toggleBtn.style.color = "#fff";
        toggleBtn.style.borderColor = "rgba(255,255,255,0.2)";
    }
}

// 0. Initialize default language on page load (BEFORE Google loads)
(function () {
    // If no googtrans cookie exists, set it to English by default
    if (!getCookie('googtrans')) {
        setCookie('googtrans', '/en/en');
    }
})();

// 1. Define Init Function (Must be global)
window.googleTranslateElementInit = function () {
    new google.translate.TranslateElement({
        pageLanguage: 'en', // Original language of your page
        includedLanguages: 'en,es', // Allowed languages
        layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
        autoDisplay: false
    }, 'google_translate_element');

    // Apply the stored language preference
    applyStoredLanguage();

    // Update the button text immediately after Google loads
    updateButtonState();
};

// 2. Inject Google Script
(function () {
    // Only inject if not already present
    if (!document.getElementById('google-translate-script')) {
        const script = document.createElement('script');
        script.id = 'google-translate-script';
        script.type = 'text/javascript';
        script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
        document.head.appendChild(script);

        // Create hidden div
        if (!document.getElementById('google_translate_element')) {
            const div = document.createElement('div');
            div.id = 'google_translate_element';
            div.style.display = 'none';
            document.body.appendChild(div);
        }
    }
})();

// 3. Main Logic
document.addEventListener("DOMContentLoaded", () => {
    const toggleBtn = document.getElementById('langToggle');

    // --- FORCE HIDE BANNER ---
    // Poll for 2 seconds to keep the banner hidden
    const intervalId = setInterval(() => {
        const iframe = document.querySelector('.goog-te-banner-frame');
        if (iframe) iframe.style.display = 'none';

        if (document.body.style.top !== "0px") {
            document.body.style.top = "0px";
            document.body.style.position = "static";
        }
    }, 100);
    setTimeout(() => clearInterval(intervalId), 2000);


    // --- TOGGLE BUTTON LOGIC ---
    if (toggleBtn) {
        // Set initial visual state
        updateButtonState();

        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();

            // Read current state
            const currentCookie = getCookie('googtrans');

            if (currentCookie === '/en/es') {
                // === CURRENTLY SPANISH -> SWITCH TO ENGLISH ===
                // We overwrite the cookie to '/en/en' explicitly
                setCookie('googtrans', '/en/en');
                console.log("Switched to English");
            } else {
                // === CURRENTLY ENGLISH -> SWITCH TO SPANISH ===
                setCookie('googtrans', '/en/es');
                console.log("Switched to Spanish");
            }

            // Reload page to apply translation
            window.location.reload();
        });
    }
});

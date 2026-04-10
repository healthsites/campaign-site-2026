document.addEventListener('DOMContentLoaded', function() {
    // Target the element where you want the animated sentence
    const targetElement = document.getElementById('animated-sentence');

    if (targetElement) {
        ityped.init(targetElement, {
            strings: [
                'Welcome to my Pelican site!',
                'Check out my latest articles.',
                'Thanks for visiting!'
            ],
            typeSpeed: 80,          // Typing speed in milliseconds
            backSpeed: 40,          // Backspacing speed
            backDelay: 2000,        // Pause before backspacing (ms)
            startDelay: 500,        // Delay before starting (ms)
            loop: true,             // Loop through strings
            cursor: true,           // Show cursor
            cursorChar: '|',        // Character for cursor
            showCursor: true,       // Display cursor
            disableBackTyping: false // Allow backspacing
        });
    }
});
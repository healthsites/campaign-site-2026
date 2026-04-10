// ============================================================================
// VANILLA HEALTHSITES.IO JAVASCRIPT
// Mobile menu, smooth scrolling, and iTyped animation
// ============================================================================

(function() {
    'use strict';

    // Single DOMContentLoaded listener
    document.addEventListener('DOMContentLoaded', function() {

        // ====================================================================
        // 1. MOBILE MENU TOGGLE
        // ====================================================================

        const mobileToggle = document.getElementById('mobile-menu-toggle');
        const mainNav = document.getElementById('main-nav');

        if (mobileToggle && mainNav) {
            // Create overlay
            const overlay = document.createElement('div');
            overlay.className = 'mobile-nav-overlay';
            document.body.appendChild(overlay);

            // Toggle menu
            mobileToggle.addEventListener('click', function(e) {
                e.preventDefault();
                mainNav.classList.toggle('active');
                overlay.classList.toggle('active');
                mobileToggle.classList.toggle('active');
                document.body.style.overflow = mainNav.classList.contains('active') ? 'hidden' : '';
            });

            // Close on overlay click
            overlay.addEventListener('click', function() {
                mainNav.classList.remove('active');
                overlay.classList.remove('active');
                mobileToggle.classList.remove('active');
                document.body.style.overflow = '';
            });

            // Close on link click
            const navLinks = mainNav.querySelectorAll('a');
            navLinks.forEach(function(link) {
                link.addEventListener('click', function() {
                    mainNav.classList.remove('active');
                    overlay.classList.remove('active');
                    mobileToggle.classList.remove('active');
                    document.body.style.overflow = '';
                });
            });

            // Close on ESC key
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape' && mainNav.classList.contains('active')) {
                    mainNav.classList.remove('active');
                    overlay.classList.remove('active');
                    mobileToggle.classList.remove('active');
                    document.body.style.overflow = '';
                }
            });
        }

        // ====================================================================
        // 2. SMOOTH SCROLL FOR ANCHOR LINKS
        // ====================================================================

        const anchorLinks = document.querySelectorAll('a[href^="#"]');

        anchorLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                const href = this.getAttribute('href');

                if (href === '#') {
                    e.preventDefault();
                    return;
                }

                const target = document.querySelector(href);

                if (target) {
                    e.preventDefault();

                    const headerHeight = document.querySelector('.site-header').offsetHeight;
                    const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;

                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        });

        // ====================================================================
        // 3. ACTIVE NAVIGATION HIGHLIGHTING
        // ====================================================================

        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.main-nav a');

        navLinks.forEach(function(link) {
            const linkPath = new URL(link.href).pathname;

            if (linkPath === currentPath ||
                (currentPath === '/' && linkPath === '/index.html') ||
                (currentPath === '/index.html' && linkPath === '/')) {
                link.style.color = 'var(--primary-color)';
                link.style.fontWeight = '700';
            }
        });

        // ====================================================================
        // 4. ITYPED - ONE-TIME TYPING ANIMATION (MULTILINGUAL)
        // ====================================================================

        const typedSubtitle = document.getElementById('typed-subtitle');

        if (typedSubtitle && typeof ityped !== 'undefined') {

            // Detect language from URL
            const isFrench = window.location.pathname.includes('/fr/');

            // Language-specific strings
            const strings = {
                en: 'healthsites.io is an open, collaborative project building a comprehensive map of health facilities worldwide to support humanitarian action and healthcare planning.',
                fr: 'healthsites.io est un projet ouvert et collaboratif construisant une carte complète des établissements de santé dans le monde entier pour soutenir l\'action humanitaire et la planification des soins de santé.'
            };

            const textToType = isFrench ? strings.fr : strings.en;

            ityped.init(typedSubtitle, {
                strings: [textToType],
                typeSpeed: 35,
                backSpeed: 0,
                backDelay: 0,
                startDelay: 300,
                showCursor: true,
                cursorChar: '|',
                loop: false,
                onFinished: function() {
                    const cursor = document.querySelector('.ityped-cursor');
                    if (cursor) {
                        cursor.style.display = 'none';
                    }
                }
            });
        }

        console.log('✓ Vanilla healthsites.io initialized');
    });
})();
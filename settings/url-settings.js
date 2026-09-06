/**
 * Inaaya's Mart - Centralized URL & Routing Settings
 * Handles clean WordPress-style trailing slashes and dynamic SPA navigation.
 */

class StoreRouter {
    constructor() {
        this.routes = [];
    }

    // Initialize routes from config or fallback
    async init() {
        try {
            const res = await fetch('/config.json');
            const config = await res.json();
            this.routes = config.storefront_routes || [];
            return this.routes;
        } catch (err) {
            console.error("Failed to load routes from config:", err);
            return [];
        }
    }

    // Convert file path to clean URL (e.g., 'pages/pet-care.html' -> '/pet-care')
    getCleanUrlPath(filePath) {
        if (!filePath) return '/';
        let clean = filePath.replace('pages/', '').replace('.html', '');
        return clean === 'home' ? '/' : `/${clean}`;
    }

    // Resolve current path to corresponding HTML file
    resolveRoute(currentPath) {
        let targetRoute = this.routes.find(r => this.getCleanUrlPath(r.path) === currentPath);
        
        if (targetRoute) {
            return {
                htmlPath: targetRoute.path,
                title: targetRoute.title
            };
        }

        // Fallback for default or dynamic paths
        if (currentPath === '/' || currentPath === '') {
            return { htmlPath: 'pages/home.html', title: 'Home' };
        }

        return {
            htmlPath: `pages${currentPath}.html`,
            title: 'Store'
        };
    }
}

// Export a global router instance
window.storeRouter = new StoreRouter();

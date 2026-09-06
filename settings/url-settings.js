/**
 * Inaaya's Mart - Centralized URL & Routing Settings
 * Handles SEO-friendly WordPress-style trailing slashes, products, and dynamic SPA navigation.
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

    // Convert file path to clean SEO-friendly URL with trailing slash (e.g., 'pages/pet-care.html' -> '/pet-care/')
    getCleanUrlPath(filePath) {
        if (!filePath) return '/';
        let clean = filePath.replace('pages/', '').replace('.html', '');
        return clean === 'home' ? '/' : `/${clean}/`;
    }

    // Normalize path by removing or ensuring trailing slashes for accurate matching
    normalizePath(path) {
        if (!path) return '/';
        // Remove trailing slash for internal comparison, except for root
        let trimmed = path !== '/' ? path.replace(/\/$/, "") : path;
        return trimmed;
    }

    // Resolve current path to corresponding HTML file and handle SEO/Dynamic Slugs (Products, Categories)
    resolveRoute(currentPath) {
        const normalizedCurrent = this.normalizePath(currentPath);

        // 1. Match against static storefront routes from config
        let targetRoute = this.routes.find(r => {
            let routeClean = this.normalizePath(this.getCleanUrlPath(r.path));
            return routeClean === normalizedCurrent;
        });
        
        if (targetRoute) {
            return {
                htmlPath: targetRoute.path,
                title: targetRoute.title,
                type: 'static'
            };
        }

        // 2. Handle Root / Home
        if (normalizedCurrent === '/' || normalizedCurrent === '') {
            return { htmlPath: 'pages/home.html', title: 'Home', type: 'home' };
        }

        // 3. SEO-Friendly Dynamic Routes for E-commerce (e.g., /product/item-name/ or /category/name/)
        const segments = normalizedCurrent.split('/').filter(Boolean);

        if (segments.length === 2) {
            const [type, slug] = segments;
            if (type === 'product') {
                return {
                    htmlPath: 'pages/product-detail.html',
                    title: 'Product Details',
                    type: 'product',
                    slug: slug
                };
            } else if (type === 'category') {
                return {
                    htmlPath: 'pages/category.html',
                    title: 'Category',
                    type: 'category',
                    slug: slug
                };
            }
        }

        // 4. Fallback for other standard pages
        return {
            htmlPath: `pages${normalizedCurrent}.html`,
            title: 'Store',
            type: 'page'
        };
    }
}

// Export a global router instance
window.storeRouter = new StoreRouter();

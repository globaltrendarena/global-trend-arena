/**
 * Inaaya's Mart - Centralized URL & Routing Settings
 * Handles SEO-friendly WordPress-style trailing slashes, products, and Parent/Child Category hierarchy.
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

    // Convert file path to clean SEO-friendly URL with trailing slash
    getCleanUrlPath(filePath) {
        if (!filePath) return '/';
        let clean = filePath.replace('pages/', '').replace('.html', '');
        return clean === 'home' ? '/' : `/${clean}/`;
    }

    // Normalize path by removing or ensuring trailing slashes
    normalizePath(path) {
        if (!path) return '/';
        let trimmed = path !== '/' ? path.replace(/\/$/, "") : path;
        return trimmed;
    }

    // Resolve current path to corresponding HTML file and handle Parent/Child Categories & Products
    resolveRoute(currentPath) {
        const normalizedCurrent = this.normalizePath(currentPath);

        // 1. Match static storefront routes from config
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

        // 3. SEO-Friendly Dynamic Routes (Products & Parent/Child Categories)
        const segments = normalizedCurrent.split('/').filter(Boolean);

        if (segments.length > 0) {
            const firstSegment = segments[0];

            // Product Detail Route: /product/item-slug/
            if (firstSegment === 'product' && segments.length === 2) {
                return {
                    htmlPath: 'pages/product-detail.html',
                    title: 'Product Details',
                    type: 'product',
                    slug: segments[1]
                };
            }

            // Parent & Child Category Route: /category/parent/ or /category/parent/child/
            if (firstSegment === 'category' && segments.length >= 2) {
                const categorySlugs = segments.slice(1); // Extracts all nested category levels
                return {
                    htmlPath: 'pages/category.html',
                    title: 'Category',
                    type: 'category',
                    slugs: categorySlugs, // e.g., ['electronics', 'smartphones']
                    parent: categorySlugs.length > 1 ? categorySlugs[categorySlugs.length - 2] : null,
                    current: categorySlugs[categorySlugs.length - 1]
                };
            }
        }

        // 4. Fallback for other pages
        return {
            htmlPath: `pages${normalizedCurrent}.html`,
            title: 'Store',
            type: 'page'
        };
    }
}

// Export a global router instance
window.storeRouter = new StoreRouter();

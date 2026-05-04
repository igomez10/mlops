# Frontend

React + TypeScript + Vite frontend for the post scanning and eBay draft workflow.

## Scripts

```bash
npm run dev
npm run build
npm run test
npm run test:e2e
```

## API Base URL

Set `VITE_API_BASE_URL` to point at the backend when the frontend is not served from the same origin.

- unset or empty: same-origin API
- example: `VITE_API_BASE_URL=http://127.0.0.1:8000`

## Notes

- The main UI lives in `src/pages/AppPage.tsx` and `src/components/PostList.tsx`.
- Playwright tests use the fixtures under `e2e/`.

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.js`. The page auto-updates as you edit the file.

## VoteLens preview

From this directory, run `npm ci` and `npm run dev`. The preview runs without the FastAPI server.

- Start at the home page. Hover or focus a state on the desktop map for a tooltip, then select it on the map or with the state picker.
- Select a fictional senator to preview their profile and open their dossier. In Texas, switch to **All sample votes** to filter by position or date.
- Open a sample policy to see its tally, related headline, and example AI response.
- At mobile widths, tap the map or use the state picker for smaller states. Navigation moves to the bottom.

Votes, headlines, and AI responses are fictional demo content. Every state has two fictional profiles, with sample votes available in the Texas demo.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

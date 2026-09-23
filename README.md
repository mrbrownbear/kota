# KOTA local static clone

The captured site, media, fonts, Next assets, route payloads and animation dependencies are served from the repository. Vercel applies a strict Content Security Policy that only permits runtime connections and resources from the deployed origin.

## Run locally

```bash
npm start
```

Open `http://127.0.0.1:8000`.

The included Node server supports clean routes, captured Next RSC requests and byte range delivery for local video files.

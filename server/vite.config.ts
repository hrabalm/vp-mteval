import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from '@tanstack/router-plugin/vite';
import react from "@vitejs/plugin-react";
import litestar from "litestar-vite-plugin";
import path from 'path';
import { defineConfig } from "vite";

const ASSET_URL = process.env.ASSET_URL || "/static/";
const VITE_PORT = process.env.VITE_PORT || "5173";
const VITE_HOST = process.env.VITE_HOST || "localhost";
export default defineConfig({
  base: `${ASSET_URL}`,
  server: {
    host: "0.0.0.0",
    port: +`${VITE_PORT}`,
    // cors: {
    //   origin: "http://localhost:8000",
    //   methods: "GET,HEAD,PUT,PATCH,POST,DELETE",
    //   credentials: true
    // },
    cors: true,
    hmr: {
      host: `${VITE_HOST}`,
    },
  },
  plugins: [
    litestar({
      input: [
        "resources/main.tsx",
      ],
      assetUrl: `${ASSET_URL}`,
      bundleDirectory: "public",
      resourceDirectory: "resources",
      hotFile: "public/hot"
    }),
    // Please make sure that '@tanstack/router-plugin' is passed before '@vitejs/plugin-react'
    TanStackRouterVite(
      {
        target: 'react',
        autoCodeSplitting: true,
        routesDirectory: "./resources/routes",
        generatedRouteTree: "./resources/routeTree.gen.ts",
        routeFileIgnorePrefix: "-",
        quoteStyle: "single"
      }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // "@": "resources"
      '@': path.resolve(__dirname, './resources')
    },
  },
});

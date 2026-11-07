import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',use:{baseURL:'http://127.0.0.1:5173',channel:'chromium',screenshot:'on',viewport:{width:1440,height:1000}},timeout:180000});

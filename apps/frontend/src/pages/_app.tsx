import type { AppProps } from "next/app";
import Head from "next/head";
import "../styles/terminal.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>AMI Terminal — Agentic Stock Market Intelligence &amp; Prediction Platform</title>
        <meta
          name="description"
          content="Three-Tier Institutional Stock Market Intelligence, Calibrated Walk-Forward Forecasting, and Google ADK Multi-Agent Research Platform"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <Component {...pageProps} />
    </>
  );
}

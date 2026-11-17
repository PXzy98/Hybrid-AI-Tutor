import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Lazy page chunks are transformed on first use, which is slow on a cold cache.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());

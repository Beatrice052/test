import type { IntakeApiClient } from "./types";
import { mockClient } from "./mockClient";
import { realClient } from "./realClient";

export const apiClient: IntakeApiClient =
  import.meta.env.VITE_API_CLIENT === "real" ? realClient : mockClient;

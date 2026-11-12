// Shared, bounded responses survive site/view switches and deduplicate callers.
// Expiry matches the short server freshness window after a dataset update.
export function responseCache<T>(capacity = 36, lifetimeMs = 300_000) {
  const values = new Map<string, { promise: Promise<T>; expires: number }>();
  return (key: string, load: () => Promise<T>): Promise<T> => {
    const hit = values.get(key);
    if (hit && hit.expires > Date.now()) {
      values.delete(key);
      values.set(key, hit);
      return hit.promise;
    }
    values.delete(key);
    const promise = load().catch((error) => {
      if (values.get(key)?.promise === promise) values.delete(key);
      throw error;
    });
    values.set(key, { promise, expires: Date.now() + lifetimeMs });
    while (values.size > capacity) values.delete(values.keys().next().value!);
    return promise;
  };
}

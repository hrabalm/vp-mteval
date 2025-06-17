export async function fetchNamespaces() {
    const response = await fetch('/api/v1/namespaces/');
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

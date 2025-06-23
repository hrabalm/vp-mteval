import { FixedSizeList as List } from 'react-window';
import { Button } from './ui/button';

function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(() => {
        console.log('Copied to clipboard');
    }).catch(err => {
        console.error('Failed to copy: ', err);
    });
}

export default function VirtualizedJSON({ json }: { json: string }) {
    const lines = JSON.stringify(json, null, 2).split('\n');
    return (
        <div className="relative">
            <Button variant="outline" className="absolute top-2 right-2 z-10 mx-2" onClick={() => copyToClipboard(JSON.stringify(json, null, 2))}>
                Copy to Clipboard
            </Button>
            <List
                height={2000}
                itemCount={lines.length}
                itemSize={24}
                width="100%"
            >
                {({ index }) => (
                    <div className="mt-0"><code><pre>{lines[index]}</pre></code></div>
                )}
            </List>
        </div>
    );
}

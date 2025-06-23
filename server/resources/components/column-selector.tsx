import { Button } from "./ui/button";

export default function ColumnSelector({ allColumns, selectedColumns, onSelectionChange }: {
    allColumns: string[],
    selectedColumns: string[],
    onSelectionChange: (selectedColumns: string[]) => void
}) {
    const availableColumns = allColumns.filter(column => !selectedColumns.includes(column));
    return (
        <div className="grid grid-cols-2 gap-4">
            <div>
                <h3>Visible columns</h3>
                <div className="flex flex-wrap gap-2">
                    {selectedColumns.map(column => (
                        <Button
                            key={column}
                            variant="default"
                            onClick={() => onSelectionChange(selectedColumns.filter(c => c !== column))}
                        >
                            {column}
                        </Button>
                    ))}
                </div>
            </div>
            <div>
                <h3>Available columns</h3>
                <div className="flex flex-wrap gap-2">
                    {availableColumns.map(column => (
                        <Button
                            key={column}
                            variant="outline"
                            onClick={() => onSelectionChange([...selectedColumns, column])}
                        >
                            {column}
                        </Button>
                    ))}
                </div>
            </div>
        </div>
    );

}
import { Button } from "./ui/button";
import { Table, TableHeader, TableBody, TableRow, TableCell } from "./ui/table";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Checkbox } from "./ui/checkbox";

export function ColumnSelectorTable({
    table,
}: {
    table: any,
}) {
    return (
        <>
            <div>
                <h4>Visibility</h4>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableCell>Visible</TableCell>
                            <TableCell>Column</TableCell>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {table.getAllColumns().map((column) => (
                            <TableRow key={column.id}>
                                <TableCell>
                                    <Checkbox
                                        disabled={!column.getCanHide()}
                                        checked={column.getIsVisible()}
                                        onCheckedChange={() => column.toggleVisibility()}
                                        aria-label="Toggle column visibility" />
                                </TableCell>
                                <TableCell>{column.id}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </>
    );
}

export default function ColumnSelectorDialog({
    table,
}: {
    table: any,
}) {
    return (
        <>
            <Dialog>
                <DialogTrigger asChild>
                    <Button variant="outline">Columns</Button>
                </DialogTrigger>
                <DialogContent className="overflow-y-scroll max-h-screen">
                    <DialogHeader>
                        <DialogTitle>Select Columns</DialogTitle>
                    </DialogHeader>
                    <ColumnSelectorTable
                        table={table}
                    />
                </DialogContent>
            </Dialog>
        </>)
}
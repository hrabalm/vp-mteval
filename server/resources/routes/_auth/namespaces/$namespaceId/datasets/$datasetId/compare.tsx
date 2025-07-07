import { createFileRoute, useSearch } from '@tanstack/react-router'
import { Tabs, TabsList, TabsContent, TabsTrigger } from '@/components/ui/tabs';
import { TypographyH3, TypographyH4 } from '@/components/typography'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useState } from 'react';
import { fetchRun } from '@/runs';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type CompareSearch = {
  runAId: number
  runBId: number
}

export const Route = createFileRoute(
  '/_auth/namespaces/$namespaceId/datasets/$datasetId/compare',
)({
  validateSearch: (search: Record<string, unknown>): CompareSearch => {
    return {
      runAId: Number(search?.runAId),
      runBId: Number(search?.runBId),
    }
  },
  loaderDeps: ({ search: { runAId, runBId } }) => ({ runAId, runBId }),
  loader: async ({ deps: { runAId, runBId }, params: { namespaceId } }) => {
    const runA = await fetchRun(runAId.toString(), namespaceId);
    const runB = await fetchRun(runBId.toString(), namespaceId);
    return {
      runA: runA,
      runB: runB,
    }
  },
  component: RouteComponent,
})

function Overview() {
  const search = Route.useSearch();

  let [selectedMetric, setSelectedMetric] = useState();

  const { runA, runB } = Route.useLoaderData();

  if (runA.dataset.id != runB.dataset.id) {
    throw new Error("Cannot compare runs from different datasets!")
  }

  const availableMetrics = [
    "BLEU", "chrF",  // FIXME, should be metrics present in both runs
  ]

  return <>
    <div className="grid grid-cols-2 gap-4">
      <div className="p-4">
        <TypographyH3>Run A</TypographyH3>
      </div>
      <div className="p-4">
        <TypographyH3>Run B</TypographyH3>
      </div>
      <div className="p-4 col-span-2">
        <ConfigTable runA={runA} runB={runB} />
      </div>
      <div className="p-4 col-span-2">
        <MetricsTable runA={runA} runB={runB} />
      </div>
    </div>
    <MetricSelect
      value={selectedMetric}
      onValueChange={setSelectedMetric}
      metrics={availableMetrics}
    />
    {JSON.stringify(search, null, 4)}
  </>
}

function ConfigTable({ runA, runB }) {
  const allKeys: string[] = Array.from(new Set(Object.keys(runA.config)).union(new Set(Object.keys(runB.config)))).sort()
  return <>
    <TypographyH4>Config</TypographyH4>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Run A</TableHead>
          <TableHead>Run B</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {allKeys.map((key) => {
          return <>
            <TableRow>
              <TableCell>{key}</TableCell>
              <TableCell>{JSON.stringify(runA.config[key])}</TableCell>
              <TableCell>{JSON.stringify(runB.config[key])}</TableCell>
            </TableRow>
          </>
        })}
      </TableBody>
    </Table>
  </>
}

function MetricsTable({ runA, runB }) {
  const allMetrics: string[] = Array.from(new Set(Object.keys(runA.dataset_metrics)).union(new Set(Object.keys(runB.dataset_metrics)))).sort()
  return <>
    <TypographyH4>Metrics</TypographyH4>
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Run A</TableHead>
          <TableHead>Run B</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {allMetrics.map((metric) => {
          return <>
            <TableRow>
              <TableCell>{(runA.dataset_metrics[metric] || runB.dataset_metrics[metric]).name}</TableCell>
              <TableCell>{JSON.stringify(runA.dataset_metrics[metric]?.score)}</TableCell>
              <TableCell>{JSON.stringify(runB.dataset_metrics[metric]?.score)}</TableCell>
            </TableRow>
          </>
        })}
      </TableBody>
    </Table>
  </>
}

function MetricSelect({ value, onValueChange, metrics }: { value: any, onValueChange: any, metrics: string[] }) {
  return <>
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="Select a metric" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Available Metrics</SelectLabel>
          {
            metrics.map((metric) => {
              return <SelectItem value={metric}>{metric}</SelectItem>
            })
          }
        </SelectGroup>
      </SelectContent>
    </Select>
  </>
}

function MetricsCharts() {
  return <>
    <TypographyH4>Charts</TypographyH4>
  </>
}

function Segments() {
  return <></>
}

function RouteComponent() {
  return (
    <>
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="segments">Segments</TabsTrigger>
        </TabsList>
        <TabsContent value="overview"><Overview /></TabsContent>
        <TabsContent value="segments"><Segments /></TabsContent>
      </Tabs>
    </>
  )
}

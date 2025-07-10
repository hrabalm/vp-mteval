import PageHeading from '@/components/PageHeading';
import { createFileRoute } from '@tanstack/react-router';
import ReactMarkdown from 'react-markdown';

export const Route = createFileRoute('/')({
  component: Index,
})

const markdownContent = `
### Documentation

- GitHub: [vp-mteval](https://github.com/hrabalm/vp-mteval)
- Server Sphinx Docs: [vp-mteval](https://hrabalm.github.io/vp-mteval/)
`;

function Index() {
  return (
    <>
      <PageHeading>Home</PageHeading>
      <div className="prose dark:prose-invert max-w-none">
        <ReactMarkdown>{markdownContent}</ReactMarkdown>
      </div>
    </>
  )
}
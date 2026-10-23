import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UploadCloud,
  FileText,
  Trash2,
  RotateCcw,
  Loader2,
} from "lucide-react";
import { api } from "../services/api";
import type { Document } from "../types";
import {
  PageHeading,
  ErrorBox,
  Empty,
  Badge,
  Loading,
} from "../components/Common";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
export function Documents() {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [drag, setDrag] = useState(false);
  const q = useQuery({
    queryKey: ["documents"],
    queryFn: () => api<Document[]>("/documents"),
    refetchInterval: 2500,
  });
  async function upload(files: FileList | null) {
    if (!files) return;
    setUploading(true);
    setErrors([]);
    const failures: string[] = [];
    for (const file of Array.from(files)) {
      try {
        const form = new FormData();
        form.append("file", file);
        await api("/documents/upload", { method: "POST", body: form });
      } catch (e) {
        failures.push(
          `${file.name}: ${e instanceof Error ? e.message : "Upload failed"}`,
        );
      }
    }
    setErrors(failures);
    setUploading(false);
    if (input.current) input.current.value = "";
    await client.invalidateQueries({ queryKey: ["documents"] });
  }
  const action = useMutation({
    mutationFn: ({ id, remove }: { id: string; remove: boolean }) =>
      api(`/documents/${id}${remove ? "" : "/reprocess"}`, {
        method: remove ? "DELETE" : "POST",
      }),
    onSuccess: () => client.invalidateQueries(),
  });
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / DOCUMENTS"
        title="Document library"
        description="Build the evidence base. Every entity, relationship, and answer starts here."
        action={<Badge>{q.data?.length ?? 0} documents</Badge>}
      />
      <Card
        className={`dropzone ${drag ? "drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!uploading) void upload(e.dataTransfer.files);
        }}
      >
        <UploadCloud size={34} />
        <h2>Bring your knowledge together</h2>
        <p>Drop documents here, or browse your files</p>
        <Button disabled={uploading} onClick={() => input.current?.click()}>
          {uploading ? (
            <Loader2 className="spin" size={16} />
          ) : (
            <UploadCloud size={16} />
          )}{" "}
          {uploading ? "Uploading…" : "Choose files"}
        </Button>
        <small>PDF, TXT, Markdown · up to 20 MB per file · UTF-8 text</small>
        <input
          ref={input}
          hidden
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          onChange={(e) => void upload(e.target.files)}
        />
      </Card>
      {errors.map((e) => (
        <ErrorBox key={e} error={e} />
      ))}
      <ErrorBox error={q.error ?? action.error} />
      <Card className="table-card">
        <div className="section-heading">
          <h2>All documents</h2>
          <span className="muted small">
            Processing status updates automatically
          </span>
        </div>
        {q.isPending ? (
          <Loading />
        ) : !q.data?.length ? (
          <Empty>
            Upload the three files in datasets/demo to explore a known three-hop
            chain.
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Status</th>
                  <th>Chunks</th>
                  <th>Size</th>
                  <th>Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <div className="file-name">
                        <FileText size={18} />
                        <a href={`/api/documents/${d.id}/source`}>{d.name}</a>
                      </div>
                      {d.error && <p className="error-text">{d.error}</p>}
                      {!!d.processing_metadata?.extraction_diagnostics?.rejected_relationship_count && (
                        <p className="notice" role="status">
                          {d.processing_metadata.extraction_diagnostics.rejected_relationship_count} invalid
                          relationship(s) discarded. Valid extracted facts were retained; graph coverage
                          may be incomplete. Details are available in document metadata.
                        </p>
                      )}
                    </td>
                    <td>
                      <span className={`status ${d.status}`}>{d.status}</span>
                      {!["ready", "failed"].includes(d.status) && (
                        <progress value={d.progress} max={100} />
                      )}
                    </td>
                    <td>{d.chunks}</td>
                    <td>{(d.size / 1024).toFixed(1)} KB</td>
                    <td>{new Date(d.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="flex gap-2">
                        <Button
                          title="Reprocess document"
                          aria-label={`Reprocess ${d.name}`}
                          variant="ghost"
                          size="sm"
                          disabled={
                            action.isPending ||
                            !["ready", "failed"].includes(d.status)
                          }
                          onClick={() =>
                            action.mutate({ id: d.id, remove: false })
                          }
                        >
                          <RotateCcw size={15} />
                        </Button>
                        <Button
                          aria-label={`Delete ${d.name}`}
                          title="Delete document"
                          variant="ghost"
                          size="sm"
                          disabled={
                            action.isPending ||
                            !["ready", "failed"].includes(d.status)
                          }
                          onClick={() => {
                            if (confirm(`Delete ${d.name} and its evidence?`))
                              action.mutate({ id: d.id, remove: true });
                          }}
                        >
                          <Trash2 size={15} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

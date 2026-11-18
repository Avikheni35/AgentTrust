"use client";

import clsx from "clsx";
import {
  FileText,
  Loader2,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, updateSensitivity, uploadDocument } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Document } from "@/lib/types";

const SENSITIVITY_COLORS: Record<string, string> = {
  public:       "bg-green-100 text-green-700",
  internal:     "bg-blue-100 text-blue-700",
  confidential: "bg-amber-100 text-amber-700",
  restricted:   "bg-red-100 text-red-700",
};

export default function DocumentsPage() {
  const { token } = useAuth();
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload form state
  const [sensitivity, setSensitivity] = useState("internal");
  const [department, setDepartment] = useState("");
  const [accessRoles, setAccessRoles] = useState("");

  async function refresh() {
    if (!token) return;
    setLoading(true);
    try { setDocs(await listDocuments(token)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to load"); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, [token]); // eslint-disable-line

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || !token) return;
    setUploading(true);
    setError(null);
    setSuccess(null);
    let count = 0;
    for (const file of Array.from(files)) {
      try {
        const res = await uploadDocument(token, file, { sensitivity, department, access_roles: accessRoles });
        count++;
        setSuccess(`Indexed "${file.name}" — ${res.chunk_count} chunks`);
      } catch (e: unknown) {
        setError(`Failed to upload "${file.name}": ${e instanceof Error ? e.message : "unknown error"}`);
      }
    }
    if (count > 0) await refresh();
    setUploading(false);
  }, [token, sensitivity, department, accessRoles]); // eslint-disable-line

  async function handleSensitivity(id: string, sensitivity: string) {
    if (!token) return;
    try {
      await updateSensitivity(token, id, sensitivity);
      setDocs((prev) => prev.map((d) => d.id === id ? { ...d, sensitivity } : d));
      setSuccess(`Sensitivity updated to "${sensitivity}"`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!token || !confirm(`Delete "${name}"?`)) return;
    try {
      await deleteDocument(token, id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Documents</h1>
        <p className="text-sm text-gray-500">Upload documents to make them searchable by the AI — permissions are enforced at retrieval time.</p>
      </div>

      {/* Upload area */}
      <div className="mb-8 rounded-xl border-2 border-dashed border-gray-300 bg-white p-8 transition-colors"
        style={{ borderColor: dragOver ? "#3b82f6" : undefined, background: dragOver ? "#eff6ff" : undefined }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
      >
        <div className="text-center">
          <UploadCloud className="mx-auto mb-3 h-10 w-10 text-gray-400" />
          <p className="mb-1 text-sm font-medium text-gray-700">Drag and drop files here</p>
          <p className="mb-4 text-xs text-gray-400">PDF, DOCX, TXT, MD supported</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {uploading ? (
              <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Uploading…</span>
            ) : "Browse files"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        {/* Metadata fields */}
        <div className="mt-6 grid grid-cols-3 gap-4 border-t border-gray-200 pt-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Sensitivity</label>
            <select
              value={sensitivity}
              onChange={(e) => setSensitivity(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500"
            >
              <option value="public">Public</option>
              <option value="internal">Internal</option>
              <option value="confidential">Confidential</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Department</label>
            <input
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="e.g. finance"
              className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Access Roles</label>
            <input
              value={accessRoles}
              onChange={(e) => setAccessRoles(e.target.value)}
              placeholder="role1, role2"
              className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {error && <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">{success}</div>}

      {/* Documents table */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="border-b border-gray-100 px-5 py-3">
          <span className="text-sm font-medium text-gray-700">{docs.length} document{docs.length !== 1 ? "s" : ""} indexed</span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : docs.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">
            <FileText className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            No documents indexed yet
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wide">
              <tr>
                <th className="px-5 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Source</th>
                <th className="px-4 py-3 text-left">Sensitivity</th>
                <th className="px-4 py-3 text-left">Chunks</th>
                <th className="px-4 py-3 text-left">Indexed</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 font-medium text-gray-900 max-w-xs truncate">{doc.name}</td>
                  <td className="px-4 py-3 text-gray-500">{doc.source_system}</td>
                  <td className="px-4 py-3">
                    <select
                      value={doc.sensitivity}
                      onChange={(e) => handleSensitivity(doc.id, e.target.value)}
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-xs font-medium border-0 cursor-pointer outline-none",
                        SENSITIVITY_COLORS[doc.sensitivity] ?? SENSITIVITY_COLORS.internal
                      )}
                    >
                      <option value="public">public</option>
                      <option value="internal">internal</option>
                      <option value="confidential">confidential</option>
                      <option value="restricted">restricted</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {doc.indexed_at ? new Date(doc.indexed_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(doc.id, doc.name)}
                      className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

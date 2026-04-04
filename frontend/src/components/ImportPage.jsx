import { useState, useRef } from "react";
import { getAuthToken } from "../auth.jsx";

const API_BASE = import.meta.env.VITE_API_URL || '';

// Chrome styling (matches HistoryPage.jsx)
const chrome = {
  titleBar: "#2e2218",
  toolbar: "#241a12",
  previewBg: "#ccc8c4",
  border: "#4a3828",
  mutedText: "#a08878",
  brightText: "#e8d8cc"
};

function tint(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/**
 * ImportPage - Drag-and-drop folder upload for Lisa's historical invoices
 *
 * Accepts folders containing sidecar JSON files alongside PDFs:
 * - invoice-001.pdf + invoice-001.json
 * - invoice-002.pdf + invoice-002.json
 *
 * Uploads to /api/import, which populates DynamoDB and stores PDFs in S3.
 */
export default function ImportPage({ config, onBack }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [results, setResults] = useState(null);
  const fileInputRef = useRef(null);

  const accent = config?.accent || "#b76e79";

  /**
   * Parse folder contents and match PDFs with sidecar JSON files
   * Returns array of { pdfFile, jsonFile, basename } objects
   *
   * The sidecar pattern expects matching file pairs:
   * - invoice-001.pdf + invoice-001.json
   * - invoice-002.pdf + invoice-002.json
   */
  const parseFolder = (files) => {
    const fileMap = {};

    // Group files by basename (without extension) to find matching pairs
    Array.from(files).forEach(file => {
      const name = file.name;
      const ext = name.substring(name.lastIndexOf('.')).toLowerCase();
      const basename = name.substring(0, name.lastIndexOf('.'));

      if (!fileMap[basename]) {
        fileMap[basename] = {};
      }

      if (ext === '.pdf') {
        fileMap[basename].pdf = file;
      } else if (ext === '.json') {
        fileMap[basename].json = file;
      }
    });

    // Filter to only pairs that have both PDF and JSON
    const pairs = [];
    const errors = [];

    Object.entries(fileMap).forEach(([basename, files]) => {
      if (files.pdf && files.json) {
        // Valid pair - both files present
        pairs.push({
          pdfFile: files.pdf,
          jsonFile: files.json,
          basename
        });
      } else if (files.pdf && !files.json) {
        // PDF without matching JSON - report as error
        errors.push(`Missing JSON for ${basename}.pdf`);
      } else if (files.json && !files.pdf) {
        // JSON without matching PDF - report as error
        errors.push(`Missing PDF for ${basename}.json`);
      }
    });

    return { pairs, errors };
  };

  /**
   * Upload folder contents to the import API
   */
  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setResults(null);

    try {
      const { pairs, errors: parseErrors } = parseFolder(files);

      if (pairs.length === 0) {
        setResults({
          success: false,
          message: 'No valid invoice pairs found',
          errors: parseErrors
        });
        setUploading(false);
        return;
      }

      setProgress({ current: 0, total: pairs.length });

      // Process each pair and upload to API
      const formData = new FormData();

      // Validate each JSON file before uploading to catch errors early
      for (let i = 0; i < pairs.length; i++) {
        const pair = pairs[i];

        // Update progress as we process each file
        setProgress({ current: i + 1, total: pairs.length });

        // Read and parse JSON file to validate structure before upload
        const jsonText = await pair.jsonFile.text();
        try {
          const jsonData = JSON.parse(jsonText);

          // Validate required fields (invoiceNumber, date, amount)
          // These are minimum requirements - server will do more thorough validation
          if (!jsonData.invoiceNumber || !jsonData.date || !jsonData.amount) {
            parseErrors.push(`Invalid JSON for ${pair.basename}: missing required fields`);
            continue;
          }

          // Add files to form data for multipart upload
          formData.append('pdfs', pair.pdfFile, pair.basename + '.pdf');
          formData.append('jsons', pair.jsonFile, pair.basename + '.json');

        } catch (err) {
          parseErrors.push(`Malformed JSON for ${pair.basename}: ${err.message}`);
        }
      }

      // Send to API
      const token = await getAuthToken();
      const response = await fetch(`${API_BASE}/api/import`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      const result = await response.json();

      if (response.ok) {
        setResults({
          success: true,
          imported: result.imported || 0,
          failed: result.failed || 0,
          errors: [...parseErrors, ...(result.errors || [])],
          message: `Successfully imported ${result.imported} invoices`
        });
      } else {
        setResults({
          success: false,
          message: result.error || 'Import failed',
          errors: parseErrors
        });
      }

    } catch (err) {
      console.error('Import error:', err);
      setResults({
        success: false,
        message: `Import failed: ${err.message}`,
        errors: []
      });
    } finally {
      setUploading(false);
      setProgress({ current: 0, total: 0 });
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    // Access files from dataTransfer
    const items = e.dataTransfer.items;
    const files = [];

    // Collect all files from the drop
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      }
    }

    if (files.length > 0) {
      handleUpload(files);
    }
  };

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleUpload(files);
    }
  };

  return (
    <div style={{
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: chrome.titleBar,
      overflow: "hidden"
    }}>
      {/* Toolbar */}
      <div style={{
        background: chrome.toolbar,
        borderBottom: `1px solid ${chrome.border}`,
        padding: "10px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        flexShrink: 0
      }}>
        <button
          onClick={onBack}
          style={{
            fontSize: 15,
            color: chrome.mutedText,
            background: "none",
            border: `1px solid ${chrome.border}`,
            borderRadius: 6,
            padding: "5px 12px",
            cursor: "pointer"
          }}
        >
          ← Back
        </button>
        <span style={{
          fontSize: 14,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: accent,
          display: "flex",
          alignItems: "center",
          gap: 6
        }}>
          <span>📥</span> Import Historical Invoices
        </span>
      </div>

      {/* Content Area */}
      <div style={{
        flex: 1,
        overflow: "auto",
        padding: 40,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 30
      }}>
        {/* Instructions */}
        <div style={{
          maxWidth: 600,
          color: chrome.brightText,
          fontSize: 15,
          lineHeight: 1.6
        }}>
          <h2 style={{ color: accent, fontSize: 22, marginBottom: 16 }}>
            Import Your Existing Invoices
          </h2>
          <p style={{ marginBottom: 12 }}>
            Upload a folder containing your historical invoices. Each invoice should have:
          </p>
          <ul style={{ marginLeft: 20, marginBottom: 16 }}>
            <li>A PDF file (e.g., <code style={{ background: tint(accent, 0.1), padding: "2px 6px", borderRadius: 3 }}>invoice-001.pdf</code>)</li>
            <li>A matching JSON file with the same name (e.g., <code style={{ background: tint(accent, 0.1), padding: "2px 6px", borderRadius: 3 }}>invoice-001.json</code>)</li>
          </ul>
          <p style={{ fontSize: 13, color: chrome.mutedText }}>
            The JSON file should contain invoice metadata: <code>invoiceNumber</code>, <code>date</code>,
            <code>clientName</code>, <code>hours</code>, <code>rate</code>, and <code>amount</code>.
          </p>
        </div>

        {/* Drop Zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            width: "100%",
            maxWidth: 600,
            minHeight: 300,
            border: `2px dashed ${dragActive ? accent : chrome.border}`,
            borderRadius: 12,
            background: dragActive ? tint(accent, 0.05) : chrome.previewBg,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            cursor: "pointer",
            transition: "all 0.2s",
            padding: 40
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            webkitdirectory=""
            directory=""
            style={{ display: "none" }}
            onChange={handleFileSelect}
          />

          <div style={{ fontSize: 48 }}>📁</div>
          <div style={{
            fontSize: 18,
            fontWeight: 600,
            color: chrome.brightText,
            textAlign: "center"
          }}>
            {uploading ? "Uploading..." : "Drop folder here or click to browse"}
          </div>
          <div style={{
            fontSize: 13,
            color: chrome.mutedText,
            textAlign: "center"
          }}>
            Select a folder containing PDF and JSON file pairs
          </div>
        </div>

        {/* Progress Indicator */}
        {uploading && progress.total > 0 && (
          <div style={{
            width: "100%",
            maxWidth: 600,
            padding: 20,
            background: chrome.toolbar,
            border: `1px solid ${chrome.border}`,
            borderRadius: 8
          }}>
            <div style={{
              fontSize: 15,
              color: chrome.brightText,
              marginBottom: 12
            }}>
              Processing: {progress.current} of {progress.total} files
            </div>
            <div style={{
              width: "100%",
              height: 8,
              background: chrome.border,
              borderRadius: 4,
              overflow: "hidden"
            }}>
              <div style={{
                width: `${(progress.current / progress.total) * 100}%`,
                height: "100%",
                background: accent,
                transition: "width 0.3s"
              }} />
            </div>
          </div>
        )}

        {/* Results */}
        {results && (
          <div style={{
            width: "100%",
            maxWidth: 600,
            padding: 24,
            background: results.success ? tint(accent, 0.1) : tint("#d44", 0.1),
            border: `1px solid ${results.success ? accent : "#d44"}`,
            borderRadius: 8
          }}>
            <div style={{
              fontSize: 18,
              fontWeight: 600,
              color: results.success ? accent : "#d44",
              marginBottom: 12
            }}>
              {results.success ? "✓ Import Complete" : "✗ Import Failed"}
            </div>
            <div style={{
              fontSize: 15,
              color: chrome.brightText,
              marginBottom: results.errors?.length > 0 ? 16 : 0
            }}>
              {results.message}
            </div>

            {results.errors && results.errors.length > 0 && (
              <div>
                <div style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: chrome.mutedText,
                  marginBottom: 8
                }}>
                  Issues encountered:
                </div>
                <ul style={{
                  margin: 0,
                  paddingLeft: 20,
                  fontSize: 13,
                  color: chrome.mutedText
                }}>
                  {results.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {results.success && (
              <button
                onClick={onBack}
                style={{
                  marginTop: 20,
                  padding: "10px 20px",
                  background: accent,
                  color: "white",
                  border: "none",
                  borderRadius: 6,
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                View History
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

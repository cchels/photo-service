// script.js

// --- Configuration ---
const API_KEY      = 'ZUbqHmgKrF5aWiUhCYpnCaxe3M5lhiQkaIdfVGml';
const API_BASE_URL = 'https://08yc4gdt36.execute-api.us-east-1.amazonaws.com/prod';

// Initialize the API Gateway client for search only
const apigClient = apigClientFactory.newClient({
  apiKey: API_KEY
});

// DOM references
const resultsEl   = document.getElementById('searchResults');
const statusEl    = document.getElementById('uploadStatus');
const fileInput   = document.getElementById('fileInput');
const customInput = document.getElementById('customLabelsInput');

// --- SEARCH HANDLER ---
document.getElementById('searchBtn').addEventListener('click', () => {
  const q = document.getElementById('searchInput').value.trim();
  if (!q) return;

  // Call GET /search?q={q} using the SDK
  apigClient.searchGet({ q }, {}, {})
    .then(res => {
      const items = (res.data && res.data.results) || [];
      if (items.length) {
        resultsEl.innerHTML = items.map(photo => `
          <div class="image-card">
            <img src="${photo.url}" alt="" />
            <div class="labels">${photo.labels.join(', ')}</div>
          </div>
        `).join('');
      } else {
        resultsEl.innerHTML = '<p>No photos found.</p>';
      }
    })
    .catch(err => {
      console.error('Search error', err);
      resultsEl.innerHTML = `<p>Error: ${err.message}</p>`;
    });
});

// --- UPLOAD HANDLER (bypass SDK) ---
document.getElementById('uploadBtn').addEventListener('click', () => {
  if (!fileInput.files.length) {
    alert('Select a file');
    return;
  }
  const file   = fileInput.files[0];
  const custom = customInput.value.trim();

  // Log file details for debugging
  console.log('Uploading file:', file.name, file.size, file.type);

  // Construct the upload URL with query-string filename
  const uploadUrl = `${API_BASE_URL}/upload?filename=${encodeURIComponent(file.name)}`;

  // Perform the PUT via fetch, streaming the File blob
  fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      'x-api-key':               API_KEY,
      'Content-Type':            file.type,
      'x-amz-meta-customLabels': custom
    },
    body: file
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
    }
    statusEl.textContent = 'Upload successful!';
    fileInput.value = '';
    customInput.value = '';
    // Optionally clear previous search results
    // resultsEl.innerHTML = '';
  })
  .catch(err => {
    console.error('Upload error', err);
    statusEl.textContent = `Error: ${err.message}`;
  });
});

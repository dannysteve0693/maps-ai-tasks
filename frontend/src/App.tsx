// App.tsx
import React, { useState, useEffect, useCallback } from 'react';

// Define the new shape of the data expected from the backend API
interface MapApiResponse {
  original_prompt: string;
  llm_query_extracted: string;
  Maps_interactive_link: string;
  Maps_embed_iframe_url: string;
  error?: string; // Optional error message
}

// Main App component
function App() {
  // State for the user's input query
  const [query, setQuery] = useState<string>('');
  // State for the embedded map URL (now Maps_embed_iframe_url)
  const [mapUrl, setMapUrl] = useState<string>('');
  // State for the directions URL (now Maps_interactive_link)
  const [directionsUrl, setDirectionsUrl] = useState<string>('');
  // State to display the found location name (now llm_query_extracted), initialized as null
  const [locationName, setLocationName] = useState<string | null>(null);
  // State to manage loading indicator
  const [loading, setLoading] = useState<boolean>(false);
  // State to manage error messages, initialized as null
  const [error, setError] = useState<string | null>(null);

  // Base URL for your Python backend
  // Still pointing to port 8080
  const BACKEND_URL: string = 'http://localhost:8080';

  // Function to handle fetching map data from the backend
  // Using useCallback to memoize the function, preventing unnecessary re-creations
  const fetchMap = useCallback(async () => {
    setError(null); // Clear any previous errors
    setMapUrl(''); // Clear previous map
    setDirectionsUrl(''); // Clear previous directions
    setLocationName(null); // Clear previous location name

    if (!query.trim()) { // Check if query is empty or just whitespace
      setError('Please enter a place or address to search.');
      return;
    }

    setLoading(true); // Set loading to true
    try {
      // Changed to POST request
      const response = await fetch(`${BACKEND_URL}/places`, {
        method: 'POST', // Specify POST method
        headers: {
          'Content-Type': 'application/json', // Indicate JSON content in the body
          "X-API-Key": "hello-world",
        },
        body: JSON.stringify({ prompt: query }), // Send the query in the request body as JSON
      });
      
      // Parse the JSON response, casting it to our defined interface
      const data: MapApiResponse = await response.json();

      if (response.ok) {
        // Update states with data from a successful response based on the new schema
        setMapUrl(data.Maps_embed_iframe_url);
        setDirectionsUrl(data.Maps_interactive_link);
        setLocationName(data.llm_query_extracted); // Use llm_query_extracted for location name display
      } else {
        // Set error message based on backend response or a generic one
        // Assuming backend will still send an 'error' field on failure
        setError(data.error || 'Failed to fetch map data. Please try again.');
      }
    } catch (err) {
      // Log the full error for debugging purposes
      console.error('Error fetching map:', err);
      // Provide a user-friendly error message
      setError('An error occurred while connecting to the map service. Please ensure the backend is running and try again.');
    } finally {
      setLoading(false); // Set loading to false regardless of success or failure
    }
  }, [query]); // Re-create fetchMap if query changes

  // Effect to handle keyboard 'Enter' key press for initiating map search
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // Check if the pressed key is 'Enter'
      if (event.key === 'Enter') {
        fetchMap(); // Call the memoized fetchMap function
      }
    };
    // Add event listener to the window
    window.addEventListener('keypress', handleKeyPress);
    // Cleanup function to remove the event listener when the component unmounts or dependencies change
    return () => {
      window.removeEventListener('keypress', handleKeyPress);
    };
  }, [fetchMap]); // Dependency array includes fetchMap, ensuring the latest version is used

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4 font-sans">
      <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-4xl border border-gray-200">
        <h1 className="text-4xl font-extrabold text-gray-800 mb-6 text-center">
          LLM-Powered Map Explorer
        </h1>

        <p className="text-gray-600 text-lg mb-8 text-center">
          Enter a location, landmark, or type of place (e.g., "Eiffel Tower", "Best pizza in New York")
          to view it on Google Maps.
        </p>

        {/* Input and Button Section */}
        <div className="flex flex-col sm:flex-row gap-4 mb-8">
          <input
            type="text"
            className="flex-grow p-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg shadow-sm transition duration-200 ease-in-out"
            placeholder="Search for a place (e.g., Tokyo Skytree, cafes in Paris)"
            value={query}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
            aria-label="Location search input"
          />
          <button
            onClick={fetchMap}
            disabled={loading}
            className="px-8 py-4 bg-blue-600 text-white font-semibold rounded-xl shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-75 transition duration-300 ease-in-out transform hover:scale-105 disabled:opacity-60 disabled:cursor-not-allowed text-lg"
          >
            {loading ? 'Loading...' : 'Get Map'}
          </button>
        </div>

        {/* Error Message Display */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-xl mb-6 shadow-sm" role="alert">
            <strong className="font-bold mr-2">Error!</strong>
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        {/* Map Display Area */}
        {mapUrl && (
          <div className="mt-8 bg-gray-50 rounded-2xl p-6 shadow-lg border border-gray-200">
            <h2 className="text-3xl font-bold text-gray-700 mb-5 text-center">
              Map for: <span className="text-blue-600">{locationName || query}</span>
            </h2>
            <div className="relative pt-[56.25%] mb-6 rounded-xl overflow-hidden shadow-lg"> {/* 16:9 Aspect Ratio */}
              <iframe
                title="Google Map"
                src={mapUrl}
                className="absolute top-0 left-0 w-full h-full border-0 rounded-xl"
                allowFullScreen={false}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                aria-label={`Embedded map of ${locationName || query}`}
              ></iframe>
            </div>
            <div className="text-center">
              <a
                href={directionsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-6 py-3 bg-green-600 text-white font-semibold rounded-xl shadow-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-opacity-75 transition duration-300 ease-in-out transform hover:scale-105 text-lg"
                aria-label={`Open directions for ${locationName || query} in Google Maps`}
              >
                <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-8a1 1 0 001 1h2a1 1 0 100-2h-2a1 1 0 00-1 1z" clipRule="evenodd"></path>
                </svg>
                Get Directions in Google Maps
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

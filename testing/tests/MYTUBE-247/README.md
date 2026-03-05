# MYTUBE-247 Test

## Objective
Verify that the Video.js player is not initialized and no HLS manifest is requested when the video status is not 'ready'.

## Steps
1. Seed a video with status 'processing' in the test database
2. Navigate to the video watch page at `/v/[video_id]`
3. Verify the "Video not available yet." message is displayed
4. Verify the Video.js player is not initialized
5. Verify no HLS manifest requests are made to the network

## Expected Result
- The UI displays "Video not available yet." message instead of the player
- No Video.js instance is created
- No network requests for HLS manifest are initiated

let currentPlaylist = [];
let currentIndex = -1;
let currentSong = null; // Currently playing song, independent of currentPlaylist
let audio = document.getElementById('audio-player');
let isPlaying = false;
let lyrics = [];
let lyricLines = []; // DOM elements
let tempPlaylistInfo = {}; // To pass data between views
let currentView = null;
let currentParam = null;
let navHistory = [];
let isLoadingView = false;
let currentAbortController = null;

// --- Disable F12 and right-click ---
// Disable F12 developer tools and other function keys
function disableF12AndFunctionKeys(e) {
    // Disable F12 key
    if (e.key === 'F12') {
        e.preventDefault();
        return false;
    }
    // Disable Ctrl+Shift+I (Inspect Element)
    if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'i')) {
        e.preventDefault();
        return false;
    }
    // Disable Ctrl+Shift+J (Open DevTools to Console)
    if (e.ctrlKey && e.shiftKey && (e.key === 'J' || e.key === 'j')) {
        e.preventDefault();
        return false;
    }
    // Disable Ctrl+U (View Page Source)
    if (e.ctrlKey && (e.key === 'U' || e.key === 'u')) {
        e.preventDefault();
        return false;
    }
    // Disable Ctrl+Shift+C (Inspect Element alternative)
    if (e.ctrlKey && e.shiftKey && (e.key === 'C' || e.key === 'c')) {
        e.preventDefault();
        return false;
    }

    // Disable Ctrl+R (Refresh)
    if (e.ctrlKey && (e.key === 'R' || e.key === 'r')) {
        e.preventDefault();
        return false;
    }
}

// Disable right-click context menu
function disableRightClick(e) {
    e.preventDefault();
    return false;
}

// Add event listeners
document.addEventListener('keydown', disableF12AndFunctionKeys);
document.addEventListener('contextmenu', disableRightClick);

// --- Navigation ---
document.addEventListener('DOMContentLoaded', () => {
    navigate('toplist');
    
    // Search Listener
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const query = searchInput.value.trim();
            if (query) {
                navigate('search', query);
            }
        }
    });
    
    // Initial mini player state: no info shown
    document.getElementById('mini-cover').style.display = 'none';
    document.getElementById('mini-title').innerText = '';
    document.getElementById('mini-artist').innerText = '';
    
    // Audio Events
    audio.addEventListener('timeupdate', updateProgress);
    audio.addEventListener('ended', playNext);
    audio.addEventListener('loadedmetadata', () => {
        document.getElementById('mini-duration').innerText = formatTime(audio.duration);
        document.getElementById('fs-duration').innerText = formatTime(audio.duration);
    });
});

function navigate(view, param = null) {
    const content = document.getElementById('content-area');
    
    if (view === currentView && (param === null || param === currentParam)) return;
    if (currentAbortController) {
        try { currentAbortController.abort(); } catch(e) {}
        currentAbortController = null;
    }
    if (currentView) {
        navHistory.push({ view: currentView, param: currentParam });
        if (navHistory.length > 20) navHistory.shift();
    }
    currentView = view;
    currentParam = param;
    
    // Update Sidebar Active State
    document.querySelectorAll('.sidebar nav li').forEach(li => li.classList.remove('active'));
    if (['toplist', 'playlists', 'favorites'].includes(view)) {
        const items = document.querySelectorAll('.sidebar nav li');
        if(view === 'toplist') items[0].classList.add('active');
        if(view === 'playlists') items[1].classList.add('active');
        if(view === 'favorites') items[2].classList.add('active');
    }

    isLoadingView = true;
    if (view === 'toplist') {
        loadToplist();
    } else if (view === 'playlists') {
        loadPlaylists(param || '全部');
    } else if (view === 'playlist_detail') {
        // param should be id, info is in tempPlaylistInfo
        loadPlaylistDetail(param);
    } else if (view === 'favorites') {
        loadFavorites();
    } else if (view === 'search') {
        loadSearchResults(param);
    }
}

function navigateBack() {
    const prev = navHistory.pop();
    if (prev) {
        navigate(prev.view, prev.param);
    }
}

// --- Data Loading ---

async function loadToplist() {
    try {
        const ctrl = new AbortController();
        currentAbortController = ctrl;
        const res = await fetch('/api/163/toplist', { signal: ctrl.signal });
        const data = await res.json();

        // 检查是否还在当前视图，如果用户已切换则不渲染
        if (currentView !== 'toplist') return;

        let html = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <h2 style="margin:0;">热歌排行</h2>
        </div><div class="list-container">`;
        data.forEach((song, index) => {
            const isFav = favoriteIds.has(String(song.id));
            const heartClass = isFav ? "fas" : "far";
            const heartColor = isFav ? "#fa233b" : "#999";
            html += `
                <div class="list-item" data-song-id="${song.id}" onclick="playTopSong('${song.id}')">
                    <div id="top-img-${song.id}" class="img-skeleton skeleton"></div>
                    <div class="list-info">
                        <div class="list-title">${song.title}</div>
                        <div class="list-sub" id="top-sub-${song.id}"></div>
                    </div>
                    <div class="list-heart" style="color:${heartColor};" onclick="event.stopPropagation(); toggleFavoriteBySongId('${song.id}')"><i class="${heartClass} fa-heart"></i></div>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('content-area').innerHTML = html;
        currentPlaylist = data;
        isLoadingView = false;
        enrichToplistNoLimit(data, ctrl.signal);

        // Update currentPlaylist with enriched data after enrichment is complete
        // Using a timeout to ensure enrichment has time to update the items
        setTimeout(() => {
            // The enrichToplistNoLimit function updates the items in place
            // So currentPlaylist already contains the updated items
            // Update the heart icons to reflect favorite status
            updateListHearts();
        }, 100);
    } catch (e) {
        isLoadingView = false;
    }
}

function enrichToplistNoLimit(items, signal) {
    items.forEach(item => {
        fetch(`/api/meting?server=netease&type=song&id=${item.id}`, { signal })
            .then(r => r.json())
            .then(arr => {
                if (Array.isArray(arr) && arr.length > 0) {
                    const s = arr[0];
                    const imgEl = document.getElementById(`top-img-${item.id}`);
                    const subEl = document.getElementById(`top-sub-${item.id}`);
                    if (imgEl && s.pic) {
                        imgEl.style.backgroundImage = `url(${s.pic})`;
                        imgEl.classList.remove('skeleton');
                    }
                    if (subEl && s.author) subEl.textContent = s.author;
                    // Update item with complete song info including URL for immediate playback
                    item.title = s.title || item.title;
                    item.author = s.author || item.author;
                    item.pic = s.pic || item.pic;
                    item.url = s.url || item.url;
                    item.lrc = s.lrc || item.lrc;
                }
            }).catch(() => {});
    });
}

async function playTopSong(id) {
    try {
        // Find the song in the enriched playlist which should already have the URL
        const song = currentPlaylist.find(s => s.id === id);
        
        if (song && song.url) {
            // If the song is already in the playlist with URL, play it directly
            currentIndex = currentPlaylist.indexOf(song);
            loadSong(song);
        } else {
            // Fallback: fetch the song info if not available in current playlist
            const res = await fetch(`/api/meting?server=netease&type=song&id=${id}`);
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                currentPlaylist = data;
                currentIndex = 0;
                loadSong(data[0]);
            }
        }
    } catch (e) {
        console.error('Failed to play top song', e);
    }
}



async function loadPlaylists(cat) {
    try {
        const res = await fetch(`/api/163/playlists?cat=${cat}`);
        const data = await res.json();

        // 检查是否还在当前视图，如果用户已切换则不渲染
        if (currentView !== 'playlists') return;

        let html = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <h2 style="margin:0;">${cat} 歌单</h2>
        </div><div class="grid-container">`;
        data.forEach(pl => {
            // Escape quotes for safety
            const safeName = pl.name.replace(/'/g, "\\'");
            const safeCover = pl.cover;
            html += `
                <div class="card" onclick="openPlaylist('${pl.id}', '${safeName}', '${safeCover}')">
                    <img src="${pl.cover}" class="card-img" loading="lazy">
                    <div class="card-title">${pl.name}</div>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('content-area').innerHTML = html;
        isLoadingView = false;
    } catch (e) {
        isLoadingView = false;
    }
}

function openPlaylist(id, name, cover) {
    tempPlaylistInfo = { id, name, cover };
    navigate('playlist_detail', id);
}

async function loadPlaylistDetail(id) {
    try {
        // Immediately show header with album and title, and lock sidebar
        const title = tempPlaylistInfo.name || '歌单';
        const cover = tempPlaylistInfo.cover || '';
        let html = `
            <div style="display:flex; margin-bottom:30px; gap:20px; align-items:flex-end;">
                <button onclick="navigateBack()" style="background:none;border:none;color:#666;cursor:pointer;"><i class="fas fa-chevron-left"></i></button>
                <img src="${cover}" style="width:200px; height:200px; border-radius:10px; box-shadow:0 10px 30px rgba(0,0,0,0.2);">
                <div>
                    <div style="font-size:14px; font-weight:700; color:#fa233b; margin-bottom:10px;">PLAYLIST</div>
                    <h1 style="margin:0 0 20px 0; font-size:40px; line-height:1.2;">${title}</h1>
                </div>
            </div>
            <div class="list-container" id="pl-list"></div>
        `;
        document.getElementById('content-area').innerHTML = html;

        const ctrl = new AbortController();
        currentAbortController = ctrl;
        const res = await fetch(`/api/meting?server=netease&type=playlist&id=${id}`, { signal: ctrl.signal });
        const data = await res.json();

        // 检查是否还在当前视图，如果用户已切换则不渲染
        if (currentView !== 'playlist_detail') return;
        
        currentPlaylist = data; // Store current playlist for next/prev
        
        // Render list with skeleton placeholders
        const listEl = document.getElementById('pl-list');
        if (listEl) {
            let listHtml = '';
            data.forEach((song, index) => {
                const idAttr = song.id || ((song.url && (/id=(\d+)/.exec(song.url) || [])[1]) || `fallback-${index}`);
                const isFav = favoriteIds.has(String(idAttr));
                const heartClass = isFav ? "fas" : "far";
                const heartColor = isFav ? "#fa233b" : "#999";
                listHtml += `
                    <div class="list-item" data-song-id="${idAttr}" onclick="playSongAtIndex(${index})">
                        <div id="pl-img-${idAttr}" class="img-skeleton skeleton"></div>
                        <div class="list-info">
                            <div class="list-title" id="pl-title-${idAttr}">&nbsp;</div>
                            <div class="list-sub" id="pl-sub-${idAttr}"></div>
                        </div>
                        <div class="list-heart" style="color:${heartColor};" onclick="event.stopPropagation(); toggleFavoriteBySongId('${idAttr}')"><i class="${heartClass} fa-heart"></i></div>
                    </div>
                `;
            });
            listEl.innerHTML = listHtml;
        }
        
        isLoadingView = false;
        
        // Enrich playlist details asynchronously
        enrichPlaylistDetail(data, ctrl.signal);
        
        // Update the heart icons to reflect favorite status after enrichment
        setTimeout(() => {
            updateListHearts();
        }, 100);
        
    } catch (e) {
        document.getElementById('content-area').innerHTML = '<p>歌单加载失败</p>';
        console.error(e);
        isLoadingView = false;
    }
}

function enrichPlaylistDetail(items, signal) {
    items.forEach((item, index) => {
        const idAttr = item.id || ((item.url && (/id=(\d+)/.exec(item.url) || [])[1]) || `fallback-${index}`);
        fetch(`/api/meting?server=netease&type=song&id=${idAttr}`, { signal })
            .then(r => r.json())
            .then(arr => {
                if (Array.isArray(arr) && arr.length > 0) {
                    const s = arr[0];
                    const imgEl = document.getElementById(`pl-img-${idAttr}`);
                    const titleEl = document.getElementById(`pl-title-${idAttr}`);
                    const subEl = document.getElementById(`pl-sub-${idAttr}`);
                    if (imgEl) {
                        if (s.pic) {
                            imgEl.style.backgroundImage = `url(${s.pic})`;
                            imgEl.style.backgroundSize = 'cover';
                            imgEl.style.backgroundPosition = 'center';
                        }
                        imgEl.classList.remove('skeleton');
                    }
                    if (titleEl) {
                        if (s.title) {
                            titleEl.textContent = s.title;
                        } else {
                            titleEl.textContent = item.title || '未知歌曲';
                        }
                    }
                    if (subEl) {
                        if (s.author) {
                            subEl.textContent = s.author;
                        } else {
                            subEl.textContent = item.author || '未知艺术家';
                        }
                    }
                    item.title = s.title || item.title;
                    item.author = s.author || item.author;
                    item.pic = s.pic || item.pic;
                    item.url = s.url || item.url;
                    item.lrc = s.lrc || item.lrc;
                }
            }).catch(error => {
                console.error('Error loading song details:', error);
                // Even if API fails, ensure skeleton is removed and fallback content is shown
                const imgEl = document.getElementById(`pl-img-${idAttr}`);
                const titleEl = document.getElementById(`pl-title-${idAttr}`);
                const subEl = document.getElementById(`pl-sub-${idAttr}`);
                if (imgEl) {
                    imgEl.classList.remove('skeleton');
                    imgEl.style.backgroundColor = '#e5e5e5';
                    imgEl.style.display = 'flex';
                    imgEl.style.alignItems = 'center';
                    imgEl.style.justifyContent = 'center';
                    imgEl.innerHTML = '<i class="fas fa-music" style="color:#999;font-size:20px;"></i>';
                }
                if (titleEl && titleEl.textContent === '&nbsp;') {
                    titleEl.textContent = item.title || '未知歌曲';
                }
                if (subEl && subEl.textContent === '') {
                    subEl.textContent = item.author || '未知艺术家';
                }
            });
    });
    
    // Update the heart icons to reflect favorite status after enrichment
    setTimeout(() => {
        updateListHearts();
    }, 100);
}

async function loadFavorites() {
    try {
        const res = await fetch('/api/favorites');
        const songIds = await res.json(); // 现在返回的是 song_id 列表

        // 检查是否还在当前视图，如果用户已切换则不渲染
        if (currentView !== 'favorites') return;

        if (songIds.length === 0) {
            document.getElementById('content-area').innerHTML = '<h2>我的收藏</h2><p>暂无收藏歌曲</p>';
            currentPlaylist = [];
            isLoadingView = false;
            return;
        }
        
        // 先显示骨架屏
        let html = `
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <h2 style="margin:0;">我的收藏</h2>
                <span style="color:#999;font-size:14px;">(${songIds.length} 首)</span>
            </div>
            <div class="list-container" id="favorites-list">
        `;
        songIds.forEach((songId, index) => {
            html += `
                <div class="list-item" data-song-id="${songId}" data-index="${index}">
                    <div id="fav-img-${songId}" class="img-skeleton skeleton"></div>
                    <div class="list-info">
                        <div class="list-title" id="fav-title-${songId}">&nbsp;</div>
                        <div class="list-sub" id="fav-sub-${songId}"></div>
                    </div>
                    <div class="list-heart" style="color:#fa233b;">
                        <i class="fas fa-heart"></i>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('content-area').innerHTML = html;
        
        // 存储收藏的歌曲ID
        currentPlaylist = songIds.map(id => ({ id: String(id), _loading: true }));
        
        // 异步加载每首歌曲的详情
        const ctrl = new AbortController();
        currentAbortController = ctrl;
        await enrichFavorites(songIds, ctrl.signal);
        
        // 绑定点击事件
        songIds.forEach((songId, index) => {
            const el = document.querySelector(`[data-song-id="${songId}"]`);
            if (el) {
                el.onclick = () => playSongAtIndex(index);
                // 收藏按钮点击事件
                const heartEl = el.querySelector('.list-heart');
                if (heartEl) {
                    heartEl.onclick = (e) => {
                        e.stopPropagation();
                        toggleFavoriteBySongId(String(songId));
                    };
                }
            }
        });
        
        isLoadingView = false;
    } catch (e) {
        document.getElementById('content-area').innerHTML = '<p>加载收藏失败</p>';
        console.error(e);
        isLoadingView = false;
    }
}

async function enrichFavorites(songIds, signal) {
    // 先初始化 currentPlaylist 为所有 songId（保持顺序）
    currentPlaylist = songIds.map(id => ({ 
        id: String(id), 
        title: '加载中...',
        author: '',
        pic: '',
        url: '',
        lrc: ''
    }));
    
    const promises = songIds.map(async (songId, index) => {
        try {
            const res = await fetch(`/api/meting?server=netease&type=song&id=${songId}`, { signal });
            const arr = await res.json();
            if (Array.isArray(arr) && arr.length > 0) {
                const s = arr[0];
                
                // 更新 UI
                const imgEl = document.getElementById(`fav-img-${songId}`);
                const titleEl = document.getElementById(`fav-title-${songId}`);
                const subEl = document.getElementById(`fav-sub-${songId}`);
                
                if (imgEl && s.pic) {
                    imgEl.style.backgroundImage = `url(${s.pic})`;
                    imgEl.style.backgroundSize = 'cover';
                    imgEl.style.backgroundPosition = 'center';
                    imgEl.classList.remove('skeleton');
                }
                if (titleEl) titleEl.textContent = s.title || '未知歌曲';
                if (subEl) subEl.textContent = s.author || '未知艺术家';
                
                // 更新当前播放列表中的数据（保持顺序）
                currentPlaylist[index] = {
                    id: String(songId),
                    title: s.title || '未知歌曲',
                    author: s.author || '未知艺术家',
                    pic: s.pic || '',
                    url: s.url || '',
                    lrc: s.lrc || ''
                };
            } else {
                // API 返回空数组
                const titleEl = document.getElementById(`fav-title-${songId}`);
                if (titleEl) titleEl.textContent = '歌曲信息不可用';
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error(`加载歌曲 ${songId} 失败:`, error);
            }
            // 显示失败状态
            const imgEl = document.getElementById(`fav-img-${songId}`);
            const titleEl = document.getElementById(`fav-title-${songId}`);
            const subEl = document.getElementById(`fav-sub-${songId}`);
            
            if (imgEl) {
                imgEl.classList.remove('skeleton');
                imgEl.style.backgroundColor = '#e5e5e5';
                imgEl.innerHTML = '<i class="fas fa-music" style="color:#999;font-size:20px;"></i>';
            }
            if (titleEl) titleEl.textContent = '加载失败';
            if (subEl) subEl.textContent = '';
        }
    });
    
    await Promise.all(promises);
}

async function toggleFavoriteBySongId(songId) {
    songId = String(songId);

    try {
        const wasFavorite = favoriteIds.has(songId);

        if (wasFavorite) {
            // Remove
            const res = await fetch(`/api/favorites?id=${encodeURIComponent(songId)}`, { method: 'DELETE' });
            if (res.ok) {
                favoriteIds.delete(songId);
                updateListHearts();
                // Update mini player heart if this is the current song
                if (currentSong && String(currentSong.id) === songId) {
                    document.getElementById('mini-heart').classList.remove('fas');
                    document.getElementById('mini-heart').classList.add('far');
                    document.getElementById('mini-heart').style.color = 'inherit';
                }
            }
        } else {
            // Add - 现在只需要发送 song_id
            const res = await fetch('/api/favorites', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: songId })
            });
            if (res.ok) {
                favoriteIds.add(songId);
                updateListHearts();
                // Update mini player heart if this is the current song
                if (currentSong && String(currentSong.id) === songId) {
                    document.getElementById('mini-heart').classList.remove('far');
                    document.getElementById('mini-heart').classList.add('fas');
                    document.getElementById('mini-heart').style.color = '#fa233b';
                }
            }
        }

        // If currently on favorites view, reload it
        if (document.querySelector('.sidebar nav li:nth-child(3)').classList.contains('active')) {
            loadFavorites();
        }
    } catch (e) {
        console.error("Error toggling favorite by song id", e);
    }
}

/* removed about page */

async function loadSearchResults(query) {
    document.getElementById('content-area').innerHTML = `<h2>搜索结果: "${query}"</h2><div class="list-container" id="search-list"></div>`;

    try {
        const ctrl = new AbortController();
        currentAbortController = ctrl;
        const res = await fetch(`/api/meting?server=netease&type=search&id=${encodeURIComponent(query)}`, { signal: ctrl.signal });
        const data = await res.json();

        // 检查是否还在当前视图，如果用户已切换则不渲染
        if (currentView !== 'search' || currentParam !== query) return;
        
        currentPlaylist = data;
        
        let html = ``;
        if (data.length === 0) {
            html += '<p>未找到相关歌曲</p>';
        } else {
            data.forEach((song, index) => {
                // Sometimes search results don't have pic immediately or need different handling
                // Meting search results structure: {title, author, url, pic, lrc...}
                // If pic is missing, use placeholder
                const pic = song.pic || 'https://via.placeholder.com/40';
                const idAttr = song.id || ((song.url && (/id=(\d+)/.exec(song.url.replace(/\\/g, '')) || [])[1]) || '');
                
                const isFav = favoriteIds.has(String(idAttr));
                const heartClass = isFav ? "fas" : "far";
                const heartColor = isFav ? "#fa233b" : "#999";
                html += `
                    <div class="list-item" data-song-id="${idAttr}" onclick="playSongAtIndex(${index})">
                        <img src="${pic}" loading="lazy">
                        <div class="list-info">
                            <div class="list-title">${song.title}</div>
                            <div class="list-sub">${song.author}</div>
                        </div>
                        <div class="list-heart" style="color:${heartColor};" onclick="event.stopPropagation(); toggleFavoriteBySongId('${idAttr}')"><i class="${heartClass} fa-heart"></i></div>
                    </div>
                `;
            });
        }
        document.getElementById('search-list').innerHTML = html;
        isLoadingView = false;
        
        // Update the heart icons to reflect favorite status after a short delay to ensure favoriteIds is loaded
        setTimeout(() => {
            updateListHearts();
        }, 100);
        
    } catch (e) {
        console.error(e);
        isLoadingView = false;
    }
}

// --- Player Logic ---

function playAll() {
    if(currentPlaylist.length > 0) {
        playSongAtIndex(0);
    }
}

function playSongAtIndex(index) {
    currentIndex = index;
    const song = currentPlaylist[index];
    loadSong(song);
}

async function loadSong(song) {
    if (!song) return;

    // Save current song independently
    currentSong = song;

    // Show player bar
    const playerBar = document.querySelector('.player-bar');
    if (playerBar) playerBar.classList.add('visible');

    // Update UI immediately
    updatePlayerUI(song);
    
    try {
        // If the URL in the object is already a full URL, we can try using it.
        // However, standard Meting usage often implies hitting the API to get the playback URL if it's not direct.
        // But the Meting response from 'playlist' usually contains a 'url' field that is a link to the API itself which redirects.
        // E.g. "url": "https://api.../url?id=..."
        
        audio.src = song.url; 
        
        const playPromise = audio.play();
        if (playPromise !== undefined) {
            playPromise.then(_ => {
                isPlaying = true;
                updatePlayBtnState();
            }).catch(error => {
                console.error("Auto-play was prevented or failed:", error);
                isPlaying = false;
                updatePlayBtnState();
            });
        }
        
        // Load Lyrics
        loadLyrics(song.lrc);
        
        // Extract Colors
        const colorThief = new ColorThief();
        const img = new Image();
        img.crossOrigin = "Anonymous";
        img.src = song.pic;
        img.onload = () => {
            try {
                const color = colorThief.getColor(img);
                const rgb = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
                const rgba = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.5)`;
                
                document.documentElement.style.setProperty('--primary-color', rgb);
                document.documentElement.style.setProperty('--primary-color-dim', rgba);
                
                // Update Backgrounds
                const fsBg = document.getElementById('fs-bg');
                fsBg.style.backgroundImage = `url(${song.pic})`;
                
                // Update Shadow for album art
                const fsAlbumImg = document.querySelector('.fs-album-art img');
                if(fsAlbumImg) {
                    fsAlbumImg.style.boxShadow = `0 20px 60px ${rgba}`;
                }
                
            } catch(e) {
                // Ignore color thief errors
            }
        };
        
    } catch (e) {
        console.error("Error playing song", e);
    }
}

function updatePlayerUI(song) {
    // Mini Player
    const miniCover = document.getElementById('mini-cover');
    miniCover.src = song.pic;
    miniCover.style.display = song.pic ? 'block' : 'none';
    document.getElementById('mini-title').innerText = song.title;
    document.getElementById('mini-artist').innerText = song.author;
    
    // Full Screen Player
    document.getElementById('fs-cover').src = song.pic;
    document.getElementById('fs-title').innerText = song.title;
    document.getElementById('fs-artist').innerText = song.author;
    
    // Update Heart
    const songId = song.id || song.url;
    const key = String(songId || '');
    const isFav = (typeof favoriteIds !== 'undefined') ? favoriteIds.has(key) : false;
    const heartClass = isFav ? "fas" : "far";
    const heartColor = isFav ? "#fa233b" : "inherit";
    document.getElementById('mini-heart').className = `${heartClass} fa-heart`;
    document.getElementById('mini-heart').style.color = heartColor;
}

function togglePlay() {
    if (!audio.src) return;
    
    if (audio.paused) {
        const playPromise = audio.play();
        if (playPromise !== undefined) {
            playPromise.then(_ => {
                isPlaying = true;
                updatePlayBtnState();
            }).catch(error => {
                console.error("Play failed:", error);
            });
        }
    } else {
        audio.pause();
        isPlaying = false;
        updatePlayBtnState();
    }
}

function updatePlayBtnState() {
    const icon = isPlaying ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>';
    document.getElementById('mini-play-btn').innerHTML = icon;
    document.getElementById('fs-play-btn').innerHTML = icon;
}

function playNext() {
    if (currentPlaylist.length === 0) return;
    
    if (currentIndex < currentPlaylist.length - 1) {
        playSongAtIndex(currentIndex + 1);
    } else {
        // Loop to start
        playSongAtIndex(0); 
    }
}

function playPrev() {
    if (currentPlaylist.length === 0) return;
    
    if (currentIndex > 0) {
        playSongAtIndex(currentIndex - 1);
    } else {
        // Go to last song if at beginning
        playSongAtIndex(currentPlaylist.length - 1);
    }
}

function updateProgress() {
    const { duration, currentTime } = audio;
    if (isNaN(duration)) return;
    
    const percent = (currentTime / duration) * 100;
    document.getElementById('mini-progress').value = percent;
    document.getElementById('fs-progress-bar').value = percent;
    
    const currTimeStr = formatTime(currentTime);
    document.getElementById('mini-current-time').innerText = currTimeStr;
    document.getElementById('fs-current-time').innerText = currTimeStr;
    
    syncLyrics(currentTime);
}

// Seek
document.getElementById('mini-progress').addEventListener('input', (e) => {
    const time = (e.target.value / 100) * audio.duration;
    audio.currentTime = time;
});

document.getElementById('fs-progress-bar').addEventListener('input', (e) => {
    const time = (e.target.value / 100) * audio.duration;
    audio.currentTime = time;
});

function formatTime(s) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min}:${sec < 10 ? '0' + sec : sec}`;
}

function setVolume(val) {
    audio.volume = val;
}

// --- Lyrics ---
let shouldStartScrolling = false;
let scrollStartIndex = -1;

async function loadLyrics(url) {
    try {
        lastLyricIndex = -1;
        shouldStartScrolling = false;
        scrollStartIndex = -1;
        const res = await fetch(url);
        const text = await res.text();
        parseLyrics(text);
        const container = document.getElementById('lyrics-container');
        if (container) container.scrollTop = 0;
    } catch (e) {
        console.error("Error loading lyrics", e);
        document.getElementById('lyrics-container').innerHTML = '<p class="lyric-line">暂无歌词</p>';
    }
}

function parseLyrics(text) {
    lyrics = [];
    const lines = text.split('\n');
    const regex = /\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)/;
    
    lines.forEach(line => {
        const match = regex.exec(line);
        if (match) {
            const min = parseInt(match[1]);
            const sec = parseInt(match[2]);
            const ms = parseInt(match[3]);
            const content = match[4].trim();
            const time = min * 60 + sec + ms / 1000;
            if (content) {
                const last = lyrics[lyrics.length - 1];
                if (last && Math.abs(last.time - time) < 0.001) {
                    lyrics[lyrics.length - 1] = { time, content };
                } else {
                    lyrics.push({ time, content });
                }
            }
        }
    });
    
    renderLyrics();
}

function renderLyrics() {
    const container = document.getElementById('lyrics-container');
    container.innerHTML = '';
    lyrics.forEach((line, index) => {
        const p = document.createElement('p');
        p.className = 'lyric-line';
        p.innerText = line.content;
        p.id = `lyric-${index}`;
        p.onclick = () => {
            audio.currentTime = line.time;
        };
        container.appendChild(p);
    });
    
    container.scrollTop = 0;
}

let lastLyricIndex = -1;
function syncLyrics(time) {
    if (lyrics.length === 0) return;

    let activeIndex = -1;
    for (let i = 0; i < lyrics.length; i++) {
        if (time >= lyrics[i].time) {
            activeIndex = i;
        } else {
            break;
        }
    }

    if (activeIndex !== -1 && activeIndex !== lastLyricIndex) {
        lastLyricIndex = activeIndex;

        const previousActiveLine = document.querySelector('.lyric-line.active');
        if (previousActiveLine) {
            previousActiveLine.classList.remove('active');
        }

        const activeLine = document.getElementById(`lyric-${activeIndex}`);
        if (activeLine) {
            activeLine.classList.add('active');

            const container = document.getElementById('lyrics-container');
            if (container) {
                const containerHeight = container.clientHeight;
                const lineHeight = activeLine.offsetHeight;
                const lineTop = activeLine.offsetTop;
                const centerPosition = lineTop - (containerHeight / 2) + (lineHeight / 2);

                if (!shouldStartScrolling) {
                    const scrollTop = container.scrollTop;
                    const visibleBottom = scrollTop + containerHeight * 0.6;
                    
                    if (lineTop > visibleBottom) {
                        shouldStartScrolling = true;
                        scrollStartIndex = activeIndex;
                    }
                }

                if (shouldStartScrolling) {
                    container.scrollTop = centerPosition;
                }
            }
        }
    }
}

// --- Full Screen Player Toggle ---
function openFullScreenPlayer() {
    if (!audio.src || audio.paused || currentIndex === -1) return;
    document.getElementById('fs-player').classList.add('active');
}

function closeFullScreenPlayer() {
    document.getElementById('fs-player').classList.remove('active');
}

// --- Favorites ---
let favoriteIds = new Set();
// Initialize favorites - 现在返回的是 song_id 列表
fetch('/api/favorites').then(r => r.json()).then(data => {
    // Clear and rebuild the favoriteIds set
    favoriteIds = new Set();
    // data 现在是 song_id 数组
    if (Array.isArray(data)) {
        data.forEach(songId => {
            favoriteIds.add(String(songId));
        });
    }
    // Refresh UI if needed
    if (currentIndex !== -1 && currentPlaylist[currentIndex]) {
        updatePlayerUI(currentPlaylist[currentIndex]);
    }
    // Update any currently displayed list hearts
    updateListHearts();
}).catch(e => console.error("Failed to init favorites", e));

async function refreshFavoriteIds() {
    try {
        const r = await fetch('/api/favorites');
        const arr = await r.json();
        // Clear and rebuild the favoriteIds set from server data
        favoriteIds.clear();
        // 现在返回的是 song_id 列表
        if (Array.isArray(arr)) {
            arr.forEach(songId => {
                favoriteIds.add(String(songId));
            });
        }
        // Update hearts in list views if any are rendered
        updateListHearts();
    } catch (e) {
        console.error('Failed to refresh favorites', e);
    }
}

function updateListHearts() {
    document.querySelectorAll('.list-item').forEach(li => {
        const id = li.getAttribute('data-song-id');
        if (id) {
            const heartEl = li.querySelector('.list-heart i');
            if (!heartEl) return;
            
            const idStr = String(id);
            if (favoriteIds.has(idStr)) {
                heartEl.classList.remove('far');
                heartEl.classList.add('fas');
                heartEl.parentElement.style.color = '#fa233b';
            } else {
                heartEl.classList.remove('fas');
                heartEl.classList.add('far');
                heartEl.parentElement.style.color = '#999';
            }
        }
    });
}
async function toggleFavorite() {
    // Use currentSong instead of currentPlaylist[currentIndex]
    if (!currentSong) return;

    const song = currentSong;
    // Prefer stable numeric ID
    let songId = song.id;
    if (!songId && song.url) {
        const m = /id=(\d+)/.exec(song.url);
        if (m) songId = m[1];
    }
    if (!songId) {
        console.error('Missing song id for favorite');
        return;
    }
    songId = String(songId);

    try {
        if (favoriteIds.has(songId)) {
            // Remove
            const res = await fetch(`/api/favorites?id=${encodeURIComponent(songId)}`, { method: 'DELETE' });
            if (res.ok) {
                // Update local state immediately
                favoriteIds.delete(songId);
                document.getElementById('mini-heart').classList.remove('fas');
                document.getElementById('mini-heart').classList.add('far');
                document.getElementById('mini-heart').style.color = 'inherit';
                // Update list hearts immediately
                updateListHearts();
            }
        } else {
            // Add - 现在只需要发送 song_id
            const res = await fetch('/api/favorites', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: songId })
            });
            if (res.ok) {
                // Update local state immediately
                favoriteIds.add(songId);
                document.getElementById('mini-heart').classList.remove('far');
                document.getElementById('mini-heart').classList.add('fas');
                document.getElementById('mini-heart').style.color = '#fa233b';
                // Update list hearts immediately
                updateListHearts();
            }
        }

        // If currently on favorites view, reload it
        if (document.querySelector('.sidebar nav li:nth-child(3)').classList.contains('active')) {
            loadFavorites();
        }
    } catch (e) {
        console.error("Error toggling favorite", e);
    }
}

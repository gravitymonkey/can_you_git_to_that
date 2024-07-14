// static/main.js
/*
	1.	70, 86, 89 (Slate)
	2.	124, 162, 166 (Light Slate)
	3.	23, 38, 38 (Dark Teal)
	4.	217, 137, 67 (Orange)
	5.	217, 167, 139 (Light Coral)
	6.	89, 105, 109 (Dark Slate)
	7.	140, 178, 182 (Sky Blue)
	8.	45, 60, 60 (Dark Green)
	9.	237, 157, 77 (Tangerine)
	10.	237, 187, 159 (Peach)
	11.	204, 92, 47 (Rust)
	12.	153, 204, 204 (Pale Cyan)

*/

document.addEventListener("DOMContentLoaded", function() {
    async function fetchAuthorData() {
        url = '/author-commits?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt
        }
        const response = await fetch(url);
        const data = await response.json();
        return data;
    }
    async function fetchFileChangeData() {
        url = '/file-changes?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt       
        }
        const response = await fetch(url);
        const data = await response.json();
        return data;
    }
    async function fetchFileChangesOverTimeData() {
        url = '/commits-over-time?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt
        }

        const response = await fetch(url);
        const data = await response.json();
        return data;
    }

    async function fetchTagsFrequency(include_all) {
        url = '/tags-frequency?' + repoParent + '&repo_name=' + repoName + '&include_all=' + include_all.toString() 
        if (startAt) {
            url = url + '&startAt=' + startAt
        }
        const response = await fetch(url);
        const data = await response.json();
        return data;
    }

    async function fetchCommitsByTagWeek() {
        url = '/commits-by-tag-week?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt
        }
        const response = await fetch(url);
        const data = await response.json();
        return data;
    }

    async function fetchPullRequestsOverTimeData() {
        url = '/pull-requests-over-time?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt;
        }

        const response = await fetch(url);
        const data = await response.json();
        return data;
    }


    function createAuthorCommitChart(data) {
        const ctx = document.getElementById('author-commit-chart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(row => row.author),
                datasets: [{
                    label: 'Commits by Author',
                    data: data.map(row => row.commits),
                    backgroundColor: 'rgba(70, 86, 89, 0.5)',
                    borderColor: 'rgba(70, 86, 89, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function createFileChangesChart(data) {
        const ctx = document.getElementById('file-changes-chart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(row => row.filename),
                datasets: [{
                    label: 'Commits by Filename',
                    data: data.map(row => row.commits),
                    backgroundColor: 'rgba(124, 162, 166, 0.5)',
                    borderColor: 'rgba(124, 162, 166, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function createFileChangesOverTimeChart(data) {
        const ctx = document.getElementById('commits-over-time-chart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(row => row.date),
                datasets: [{
                    label: 'Commits by Week',
                    data: data.map(row => ({x: row.date, y: row.commits})),
                    backgroundColor: 'rgba(23, 38, 38, 0.5)',
                    borderColor: 'rgba(23, 38, 38, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    },
                    x: {
                        type: 'time', // Use 'time' instead of 'timeseries'
                        time: {
                            unit: 'month', // Adjust the unit as needed (e.g., 'day', 'week', 'month', 'year')
                            tooltipFormat: 'YYYY-MM-DD' // Format for the tooltip
                        },
                        title: {
                            display: true
                        },
                        min: 'auto',
                        offset: 'false'   
                    }
                }
            }
        });
    }

    function createTagsFrequencyChart(data) {
        const ctx = document.getElementById('tags-frequency-chart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(row => row.name),
                datasets: [{
                    label: 'Number of Commits',
                    data: data.map(row => row.commit_count),
                    backgroundColor: [
                        'rgba(70, 86, 89, 0.8)',
                        'rgba(124, 162, 166, 0.8)',
                        'rgba(23, 38, 38, 0.8)',
                        'rgba(217, 137, 67, 0.8)',
                        'rgba(217, 167, 139, 0.8)',
                        'rgba(89, 105, 109, 0.8)',
                        'rgba(140, 178, 182, 0.8)',
                        'rgba(45, 60, 60, 0.8)',
                        'rgba(237, 157, 77, 0.8)',
                        'rgba(237, 187, 159, 0.8)',
                        'rgba(204, 92, 47, 0.8)',
                        'rgba(153, 204, 204, 0.8)'
                    ],
                    borderColor: [
                        'rgba(70, 86, 89, 1)',
                        'rgba(124, 162, 166, 1)',
                        'rgba(23, 38, 38, 1)',
                        'rgba(217, 137, 67, 1)',
                        'rgba(217, 167, 139, 1)',
                        'rgba(89, 105, 109, 1)',
                        'rgba(140, 178, 182, 1)',
                        'rgba(45, 60, 60, 1)',
                        'rgba(237, 157, 77, 1)',
                        'rgba(237, 187, 159, 1)',
                        'rgba(204, 92, 47, 1)',
                        'rgba(153, 204, 204, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.raw !== null) {
                                    label += context.raw;
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }

    function populateTagCountTable(data) {
        const tableBody = document.getElementById('tag-count-table');
        tableBody.innerHTML = ''; // Clear existing rows

        data.forEach(row => {
            const tr = document.createElement('tr');
            const tdTag = document.createElement('td');
            const tdCount = document.createElement('td');

            tdTag.textContent = row.name;
            tdTag.classList.add('px-4', 'py-2', 'border');
            tdCount.textContent = row.commit_count;
            tdCount.classList.add('px-4', 'py-2', 'border');

            tr.appendChild(tdTag);
            tr.appendChild(tdCount);
            tableBody.appendChild(tr);
        });
    }

    // Add new create function for the stacked bar chart
    function createCommitsByTagWeekChart(data) {
        const ctx = document.getElementById('commits-by-tag-week-chart').getContext('2d');

        // Prepare data for the chart
        const weeks = [...new Set(data.map(item => item.week))].sort();
        const tags = [...new Set(data.flatMap(item => Object.keys(item.tags)))];
        
        const datasets = tags.map(tag => ({
            label: tag,
            data: weeks.map(week => data.find(item => item.week === week)?.tags[tag] || 0),
            backgroundColor: getRandomColor(), // Function to generate a random color
        }));

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: weeks,
                datasets: datasets
            },
            options: {
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += context.raw;
                                return label;
                            }
                        }
                    }
                },
                responsive: true,
                scales: {
                    x: {
                        stacked: true
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function getRandomColor() {
        // Random hue
        const h = Math.random();
        // Low to medium saturation (muted colors)
        const s = Math.random() * (0.5 - 0.2) + 0.2;
        // Medium to high value (brightness)
        const v = Math.random() * (0.8 - 0.5) + 0.5;
    
        // Convert HSV to RGB
        const rgb = hsvToRgb(h, s, v);
        
        // Convert RGB to hex
        const hexColor = rgbToHex(rgb[0], rgb[1], rgb[2]);
        
        return hexColor;
    }
    
    function hsvToRgb(h, s, v) {
        let r, g, b;
        
        let i = Math.floor(h * 6);
        let f = h * 6 - i;
        let p = v * (1 - s);
        let q = v * (1 - f * s);
        let t = v * (1 - (1 - f) * s);
    
        switch (i % 6) {
            case 0: r = v, g = t, b = p; break;
            case 1: r = q, g = v, b = p; break;
            case 2: r = p, g = v, b = t; break;
            case 3: r = p, g = q, b = v; break;
            case 4: r = t, g = p, b = v; break;
            case 5: r = v, g = p, b = q; break;
        }
    
        return [
            Math.floor(r * 255),
            Math.floor(g * 255),
            Math.floor(b * 255)
        ];
    }
    
    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();
    }

    function createPullRequestsOverTimeChart(data) {
        const ctx = document.getElementById('pull-requests-over-time-chart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {	
                labels: data.map(row => row.date),
                datasets: [{
                    label: 'Pull Requests by Week',
                    data: data.map(row => row.pr_count),
                    backgroundColor: 'rgba(217, 137, 67, 0.5)',
                    borderColor: 'rgba(217, 137, 67, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        stacked: true
                    },
                    x: {
                        stacked: true
                    }
                }
            }
        });
    }
    


    fetchAuthorData().then(data => {
        createAuthorCommitChart(data);
    });

    fetchFileChangeData().then(data => {
        createFileChangesChart(data)
    });

    fetchFileChangesOverTimeData().then(data => {
        createFileChangesOverTimeChart(data);
    });

    fetchTagsFrequency(false).then(data => {
        createTagsFrequencyChart(data);
    });    

    fetchTagsFrequency(true).then(data => {
        populateTagCountTable(data);
    });   
    
    fetchCommitsByTagWeek().then(data => {
        createCommitsByTagWeekChart(data);
    });    

    fetchPullRequestsOverTimeData().then(data => {
        createPullRequestsOverTimeChart(data);
    });

});
// static/main.js


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
        url = '/tags-frequency?repo_parent=' + repoParent + '&repo_name=' + repoName + '&include_all=' + include_all.toString() 
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

    async function fetchPullRequests() {
        url = '/pull-requests-recent?repo_parent=' + repoParent + '&repo_name=' + repoName        
        if (startAt) {
            url = url + '&startAt=' + startAt;
        }

        const response = await fetch(url);
        const data = await response.json();
        return data;
    }

    async function fetchSunburstData() {
        let url = '/file-churn?repo_parent=' + repoParent + '&repo_name=' + repoName;        
        if (startAt) {
            url += '&startAt=' + startAt;
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

    function createFileChangesOverTimeChart(idata) {
        timescale = idata.type
        display_timescale = "day"
        if (timescale == 'Week'){
            display_timescale = "week"
        }
        data = idata.data        
        const ctx = document.getElementById('commits-over-time-chart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(row => row.date),
                datasets: [{
                    label: 'Commits by ' + timescale,
                    data: data.map(row => ({x: row.date, y: row.commits})),
                    backgroundColor: 'rgba(23, 38, 38, 0.5)',
                    borderColor: 'rgba(23, 38, 38, 1)',
                    borderWidth: 1,
                    tension: 0.4,
                    fill: false
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
                            unit: display_timescale, // Adjust the unit as needed (e.g., 'day', 'week', 'month', 'year')                            
                            tooltipFormat: 'YYYY/MM/DD', // Format for the tooltip
                            displayFormats: {
                                day: 'MM/DD', // Adjust this format as needed to match your timescale unit
                                week: 'YYYY/MM/DD'
                             }
                        },
                        title: {
                            display: true
                        },
                        min: 'auto',
                        offset: false   
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
            tdCount.textContent = row.total_value;
            tdCount.classList.add('px-4', 'py-2', 'border');

            tr.appendChild(tdTag);
            tr.appendChild(tdCount);
            tableBody.appendChild(tr);
        });
    }

 // Define the color mappings in an external hashmap
const colorMap = {
    "tag1": {
        backgroundColor: 'rgba(70, 86, 89, 0.8)',
        borderColor: 'rgba(70, 86, 89, 1)'
    },
    "tag2": {
        backgroundColor: 'rgba(124, 162, 166, 0.8)',
        borderColor: 'rgba(124, 162, 166, 1)'
    },
    "tag3": {
        backgroundColor: 'rgba(23, 38, 38, 0.8)',
        borderColor: 'rgba(23, 38, 38, 1)'
    },
    "tag4": {
        backgroundColor: 'rgba(217, 137, 67, 0.8)',
        borderColor: 'rgba(217, 137, 67, 1)'
    },
    "tag5": {
        backgroundColor: 'rgba(217, 167, 139, 0.8)',
        borderColor: 'rgba(217, 167, 139, 1)'
    },
    "tag6": {
        backgroundColor: 'rgba(89, 105, 109, 0.8)',
        borderColor: 'rgba(89, 105, 109, 1)'
    },
    "tag7": {
        backgroundColor: 'rgba(140, 208, 182, 0.8)',
        borderColor: 'rgba(140, 208, 182, 1)'
    },
    "tag8": {
        backgroundColor: 'rgba(80, 60, 60, 0.8)',
        borderColor: 'rgba(80, 60, 60, 1)'
    },
    "tag9": {
        backgroundColor: 'rgba(247, 167, 87, 0.8)',
        borderColor: 'rgba(247, 187, 87, 1)'
    },
    "tag10": {
        backgroundColor: 'rgba(237, 187, 159, 0.8)',
        borderColor: 'rgba(237, 187, 159, 1)'
    },
    "tag11": {
        backgroundColor: 'rgba(204, 92, 47, 0.8)',
        borderColor: 'rgba(204, 92, 47, 1)'
    },
    "tag12": {
        backgroundColor: 'rgba(204, 204, 204, 0.8)',
        borderColor: 'rgba(204, 204, 204, 1)'
    }
};

function createTagsFrequencyChart(data) {
    const ctx = document.getElementById('tags-frequency-chart').getContext('2d');
    
    // Initialize maps to store background and border colors keyed by tag names
    const backgroundColorsMap = {};
    const borderColorsMap = {};

    // Populate the maps with colors from the colorMap
    let counter = 1
    data.forEach(row => {
        const tagName = "tag" + counter;
        if (colorMap[tagName]) {
            backgroundColorsMap[row.name] = colorMap[tagName].backgroundColor;
            borderColorsMap[row.name] = colorMap[tagName].borderColor;
            colorMap[row.name] = colorMap[tagName];
        } else {
            // Default colors if tag is not in colorMap
            let cx = getRandomColor();
            backgroundColorsMap[row.name] = cx;
            borderColorsMap[row.name] = cx;
            colorMap[row.name] = cx;
        }
        counter++;
    });

    // Extract backgroundColor and borderColor arrays from maps based on data
    const backgroundColors = data.map(row => backgroundColorsMap[row.name]);
    const borderColors = data.map(row => borderColorsMap[row.name]);

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(row => row.name),
            datasets: [{
                label: 'Number of Commits',
                data: data.map(row => row.total_value),
                backgroundColor: backgroundColors,
                borderColor: borderColors,
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

async function fetchInsightsSummary(which) {
    const url = '/explain';  // The endpoint for your POST request
    const payload = {
        repo_parent: repoParent,
        repo_name: repoName,
        request_type: which
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    const data = await response.json();
    return data.summary; // Assuming the server returns an object with a 'summary' field
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
//            backgroundColor: getRandomColor(), // Function to generate a random color
            backgroundColor: getFixedColor(tag), // Function to generate a random color
        }));

        const labels = weeks.map(week => {
            const [year, weekNum] = week.split('-').map(Number);
            const date = getFirstDayOfWeek(year, weekNum);
            return date.toISOString().split('T')[0]; // Format date as 'YYYY-MM-DD'
        });

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
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

    // Helper function to get the first day of the week from a year and week number
    function getFirstDayOfWeek(year, week) {
        const simple = new Date(year, 0, 1 + (week - 1) * 7);
        const dow = simple.getDay();
        const ISOweekStart = simple;
        if (dow <= 4)
            ISOweekStart.setDate(simple.getDate() - simple.getDay() + 1);
        else
            ISOweekStart.setDate(simple.getDate() + 8 - simple.getDay());
        return ISOweekStart;
    }    

    function getFixedColor(tag) {
        if (colorMap[tag]) {
            return colorMap[tag].backgroundColor;
        } else {
            return getRandomColor();
        }
    }

    function getRandomColor() {
        // Random hue
        const h = Math.random();
        // Low to medium saturation (muted colors)
        const s = Math.random() * (0.3 - 0.1) + 0.1;
        // Medium to high value (brightness)
        const v = Math.random() * (0.7 - 0.5) + 0.5;
    
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

    function createPullRequestsChart(data, startAt) {
        const tableBody = document.getElementById('pull-requests-recent');
        tableBody.innerHTML = ''; // Clear existing rows

        data.forEach(row => {
            const tr = document.createElement('tr');
            const tdDate = document.createElement('td');
            const tdTitle = document.createElement('td');
            const tdUser = document.createElement('td');
            const tdFileCount = document.createElement('td');
            const tdDescription = document.createElement('td');

            tdDate.textContent = row.date;
            tdDate.classList.add('px-4', 'py-2', 'border');
            title_link = row.pr_title + " <A HREF='" + row.pr_url + "'>&#128279</A>"
            tdTitle.innerHTML = title_link;
            tdTitle.classList.add('px-4', 'py-2', 'border');
            tdUser.textContent = row.user;
            tdUser.classList.add('px-4', 'py-2', 'border');
            tdFileCount.textContent = row.file_count;
            tdFileCount.classList.add('px-4', 'py-2', 'border');
            tdDescription.innerHTML = row.description;
            tdDescription.classList.add('px-4', 'py-2', 'border', 'overflow-hidden', 'max-h-3');

            tr.appendChild(tdDate);
            tr.appendChild(tdTitle);
            tr.appendChild(tdUser);
            tr.appendChild(tdFileCount);
            tr.appendChild(tdDescription);
            tableBody.appendChild(tr);
        });
    }

    function createSunburstChart(data, width) {
          Sunburst()
            .data(data)
            .height(600)
            .width(width)
            .excludeRoot(true)
            .label('name')
            .size('size')
            //.color((d, parent) => color(parent ? parent.data.name : null))
            .color('color')
            .tooltipTitle((d, node) => node.data.name)
            .tooltipContent((d, node) => `Churn: <i>${node.value}</i>`)
            (document.getElementById('file-sunburst'));
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
        populateTagCountTable(data);
        // you want to run this after the color-to-tag mapping is done
        fetchCommitsByTagWeek().then(data => {
                createCommitsByTagWeekChart(data);
        });    
    });    

//    fetchTagsFrequency(true).then(data => {
//        populateTagCountTable(data);
//    });   
    
//    fetchCommitsByTagWeek().then(data => {
//        createCommitsByTagWeekChart(data);
//    });    

    fetchPullRequests().then(data => {
        createPullRequestsChart(data, startAt);
    });

    fetchSunburstData().then(data => {
        resizeChart('file-sunburst', data);
        // Add a resize event listener to handle window resizing
        window.addEventListener('resize', () => resizeChart('file-sunburst', data));
    });

    function resizeChart(whichChart, data) {
        const container = document.getElementById(whichChart);
        const width = container.offsetWidth;

        // Clear the existing chart
        container.innerHTML = '';
    
        // Create the chart with the new dimensions
        console.log(whichChart)
        if (whichChart == 'file-sunburst'){
            createSunburstChart(data, width);
        }
    }  

    
    fetchInsightsSummary('author-commits-summary').then(summary => {
        document.getElementById('author-commits-summary').textContent = summary;
    });

//    fetchInsightsSummary('file-commits-summary').then(summary => {
//        document.getElementById('file-commits-summary').textContent = summary;
//    });

    fetchInsightsSummary('commit-count-by-date-summary').then(summary => {
        document.getElementById('commit-count-by-date-summary').textContent = summary;
    });


});
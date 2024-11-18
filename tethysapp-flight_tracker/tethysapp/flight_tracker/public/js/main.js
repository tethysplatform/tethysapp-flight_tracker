var viewer;
var handler;

var flightPathEntities = [];

var $airportNamePicker;
var $flightsFromAirportForm;
var $aircraftTrackerForm;
var $loadingOverlay;


function calculateDistance(start, end) {
    return Cesium.Cartesian3.distance(start, end);
}

function generateCurvePoints(start, end) {
    let heightOffset = 1000; 

    // Convert cartesian3 positions to cartographic
    let startCartographic = Cesium.Cartographic.fromCartesian(start);
    let endCartographic = Cesium.Cartographic.fromCartesian(end);

    // Create a geodesic path between the two points to get the shortest path on the globe
    let geodesic = new Cesium.EllipsoidGeodesic(startCartographic, endCartographic);
    let surfaceDistance = geodesic.surfaceDistance;

    if (isNaN(surfaceDistance) || surfaceDistance <= 0) {
        console.error("Invalid surface distance between start and end points:", surfaceDistance);
        return null;
    }

    // Calculate the number of points based on distance
    let numPoints = Math.ceil(surfaceDistance / 10000); 

    let curvePoints = [];

    for (let i = 0; i <= numPoints; i++) {
        let fraction = i / numPoints;
        let interpolatedCartographic = geodesic.interpolateUsingFraction(fraction);

        if (!interpolatedCartographic) {
            console.error("Interpolation failed at fraction:", fraction);
            continue;
        }

        // Apply latitude adjustment to create an upward arc
        let latitudeOffset = heightOffset * Math.sin(Math.PI * fraction) ** 2;  // Parabolic offset
        interpolatedCartographic.latitude += latitudeOffset / Cesium.Ellipsoid.WGS84.maximumRadius;

        // Calculate height with offset for 3D effect
        let height = Cesium.Math.lerp(
            startCartographic.height,
            endCartographic.height,
            fraction
        ) + heightOffset * Math.sin(Math.PI * fraction); // Height offset along the curve

        if (isNaN(height)) {
            console.error("Error during height calculation: ", fraction);
            continue;
        }
        
        // Create a cartesian3 position from the interpolated cartographic
        interpolatedCartographic.height = height;
        let position = Cesium.Cartesian3.fromRadians(
            interpolatedCartographic.longitude,
            interpolatedCartographic.latitude,
            interpolatedCartographic.height
        );
        curvePoints.push(position);
    }

    if (curvePoints.length === 0) {
        console.error("No valid points generated for the curve.");
        return null;
    }

    return curvePoints;
}

function addFlightPaths(flights, color) {
    // Loop through each flight and add a flight path to the map
    flights.forEach(flight => {
        // Locate the departure and arrival airport features on the map
        let allEntities = viewer.dataSources._dataSources[0]._entityCollection._entities._array;
        let departure_feature = allEntities.find(feature => feature._properties['_ICAO Code']._value == flight.departure_airport);
        let arrival_feature = allEntities.find(feature => feature._properties['_ICAO Code']._value == flight.arrival_airport);
        if (departure_feature && arrival_feature) {
            // Get airport positions
            let departurePosition = departure_feature.position.getValue(Cesium.JulianDate.now());
            let arrivalPosition = arrival_feature.position.getValue(Cesium.JulianDate.now());
            if (departurePosition && arrivalPosition) {
                // Generate curve points for the flight path between airports
                let curvePoints = generateCurvePoints(departurePosition, arrivalPosition);
                // Make sure the flight doesn't already exist on the map and curve points are valid
                if (!viewer.entities.getById(`flight-${flight.flight_id}`) && curvePoints) {
                    let flightPathEntity = viewer.entities.add({
                        id: `flight-${flight.flight_id}`,
                        name: `Flight ${flight.flight_id}`,
                        departure_airport: flight.departure_airport,
                        arrival_airport: flight.arrival_airport,
                        departure_time: flight.departure_time,
                        arrival_time: flight.arrival_time,
                        polyline: {
                            positions: curvePoints,
                            width: 12,
                            material: new Cesium.PolylineArrowMaterialProperty(color),
                            arcType: Cesium.ArcType.GEODESIC
                        },
                        description: `
                                <table class="cesium-infoBox-defaultTable">
                                    <tr><th>Departure Airport</th><td>${flight.departure_airport ? flight.departure_airport : 'N/A'}</td></tr>
                                    <tr><th>Arrival Airport</th><td>${flight.arrival_airport ? flight.arrival_airport : 'N/A'}</td></tr>
                                    <tr><th>Departure Time</th><td>${flight.departure_time}</td></tr>
                                    <tr><th>Arrival Time</th><td>${flight.arrival_time}</td></tr>
                                    <tr><th>Distance</th><td>${calculateDistance(departurePosition, arrivalPosition).toFixed(2)} meters</td></tr>
                                    <tr><th>Aircraft ID (ICAO24)</th><td>${flight.icao24}</td></tr>
                                </table>
                        `
                    });
                    flightPathEntities.push(flightPathEntity);
                } else {
                    console.warn('Invalid curvePoints or entity already exists for flight:', flight.flight_id);
                }
            } else {
                console.warn('Invalid departure or arrival position:', departurePosition, arrivalPosition);
            }
        }
    });
}

$(document).ready(function() {
    // Initialize the Cesium viewer object and event handler object
    viewer = CESIUM_MAP_VIEW.getMap();
    handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);

    // Initialize needed the jQuery objects
    $airportNamePicker = $("#airport_name");
    $flightsFromAirportForm = $("#flights-from-airport-form");
    $aircraftTrackerForm = $("#aircraft-tracker-form");
    $loadingOverlay = $("#loading-overlay");

    // Add a click event to the viewer to detect airports being selected
    handler.setInputAction(function (click) {
        let pickedObject = viewer.scene.pick(click.position);
        if (Cesium.defined(pickedObject) && Cesium.defined(pickedObject.id)) {
            // Make sure the picked object is an airport
            let entity = pickedObject.id;
            if (entity._properties && entity._properties['_marker-symbol']._value === 'airport') {
                // Update the airport name picker value
                $airportNamePicker.val(entity._properties['_ICAO Code']._value).trigger('change');
            }
        }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Form submission event handler
    $flightsFromAirportForm.submit(function(event) {
        event.preventDefault();
        // Show the loading animation
        $loadingOverlay.show();

        // Send the form data to the endpoint
        let formData = new FormData(this);
        fetch('get-flights/', {
            method: 'POST',
            body: formData
        }).then(response => {
            if (!response.ok) {
                return response.json().then(data=> {
                    throw new Error(data.error || "An unknown error ocurred.");
                });
            }
            return response.json();
        }).then(data => {
            if (data.flights.length === 0) {
                TETHYS_APP_BASE.alert("info", "No flights found.");
                return;
            } else {
                // Clear existing flight paths
                flightPathEntities.forEach(entity => viewer.entities.remove(entity));
                flightPathEntities = [];
                
                // Add the new flight paths to the map
                addFlightPaths(data.flights, Cesium.Color.RED);

                // Get the target airport feature to zoom into depending on user's choice of departure or arrival
                let allEntities = viewer.dataSources._dataSources[0]._entityCollection._entities._array;
                let targetFeature;
                if (formData.get('place') == 'departure') {
                    targetFeature = allEntities.find(feature => feature._properties['_ICAO Code']._value == data.flights[0].departure_airport).position.getValue(Cesium.JulianDate.now());
                } else {
                    targetFeature = allEntities.find(feature => feature._properties['_ICAO Code']._value == data.flights[0].arrival_airport).position.getValue(Cesium.JulianDate.now());
                }

                // Zoom into the chosen airport
                let boundingSphere = new Cesium.BoundingSphere(targetFeature, 30000); // Adjust radius as needed
                viewer.camera.flyToBoundingSphere(boundingSphere, {
                    duration: 3,
                    easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
                    offset: new Cesium.HeadingPitchRange(
                        Cesium.Math.toRadians(0.0),
                        Cesium.Math.toRadians(-90.0), // -90 for a straight-down view
                        2000000 // Distance from the target
                    )
                });
            }
        }).catch(error => {
            console.error(error);
            TETHYS_APP_BASE.alert("danger", error.message);
        }).finally(() => {
            // Hide the loading animation
            $loadingOverlay.hide();
        })
    })
     
    // Form submission event handler
    $aircraftTrackerForm.submit(function(event) {
        event.preventDefault();
        // Show the loading animation
        $loadingOverlay.show();

        // Send the form data to the endpoint
        let formData = new FormData(this);
        fetch('track-aircraft/', {
            method: 'POST',
            body: formData
        }).then(response => {
            if (!response.ok) {
                return response.json().then(data=> {
                    throw new Error(data.error || "An unknown error ocurred.");
                });
            }
            return response.json();
        }).then(data => {
            if (data.flights.length === 0) {
                TETHYS_APP_BASE.alert("info", "No flights found.");
                return;
            } else {
                // Clear existing flight paths
                flightPathEntities.forEach(entity => viewer.entities.remove(entity));
                flightPathEntities = [];

                // Add the new flight paths to the map
                addFlightPaths(data.flights, Cesium.Color.YELLOW);

                // Gather the start and end pints of each flight path
                let positions = [];
                flightPathEntities.forEach(entity => {
                    let linePositions = entity.polyline.positions.getValue(Cesium.JulianDate.now());
                    if (linePositions && linePositions.length >= 2) {
                        // Add the start and end positions of each flight path to the positions array
                        positions.push(linePositions[0]);
                        positions.push(linePositions[linePositions.length - 1]);
                    }
                    let start = linePositions[0];
                    let end = linePositions[linePositions.length - 1];
                });
                if (positions) {
                    // Zoom to include all of the flight paths in the view
                    let boundingSphere = Cesium.BoundingSphere.fromPoints(positions);
                    viewer.camera.flyToBoundingSphere(boundingSphere, {
                        duration: 3, 
                        easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
                        offset: new Cesium.HeadingPitchRange(
                            Cesium.Math.toRadians(0.0),
                            Cesium.Math.toRadians(-90.0), // -90 for a straight-down view
                            2000000 // Distance from the target
                        )
                    })
                }
            }
        }).catch(error => {
            console.error(error);
            TETHYS_APP_BASE.alert("danger", error.message);
        }).finally(() => {
            // Hide the loading animation
            $loadingOverlay.hide();
        })
    });
});
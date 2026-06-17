import numpy as np
import quaternion

class deadReckoning:
    default_acceleration = np.array([0.0, 0.0, 9.81]) # ax, ay, az, global

    def __init__(self, angular_bias=np.array([0.0, 0.0, 0.0])):
        self.position = np.array([0.0, 0.0, 0.0]) # x, y, z, global
        self.velocity = np.array([0.0, 0.0, 0.0]) # vx, vy, vz, global
        self.acceleration = np.array([0.0, 0.0, 0.0]) # ax, ay, az, global
        self.quaternion = quaternion.one

        self.angular_bias = angular_bias

        self.angle = np.array([0.0, 0.0, 0.0]) # wx, wy, wz, global

        self.prev_position = np.array([0.0, 0.0, 0.0]) # x, y, z, global
        self.prev_velocity = np.array([0.0, 0.0, 0.0]) # vx, vy, vz, global
        self.prev_acceleration = np.array([0.0, 0.0, 0.0]) # ax, ay, az, global
        self.prev_quaternion = quaternion.one
    
    def update(self, data, dt):
        local_acceleration = np.array([data["linear acceleration"]["x"], data["linear acceleration"]["y"], data["linear acceleration"]["z"]])
        local_omega = np.array([data["angular rates"]["x"], data["angular rates"]["y"], data["angular rates"]["z"]]) - self.angular_bias

        delta_rotation = quaternion.from_rotation_vector(np.radians(local_omega * dt))
        self.quaternion = self.quaternion * delta_rotation

        self.acceleration = quaternion.rotate_vectors(self.quaternion, local_acceleration)
        self.acceleration += self.default_acceleration

        self.velocity += 0.5*(self.acceleration + self.prev_acceleration) * dt
        self.position += 0.5*(self.velocity + self.prev_velocity) * dt
        self.angle += local_omega * dt

        self.prev_position = self.position.copy()
        self.prev_velocity = self.velocity.copy()
        self.prev_acceleration = self.acceleration.copy()
        self.prev_quaternion = self.quaternion.copy()
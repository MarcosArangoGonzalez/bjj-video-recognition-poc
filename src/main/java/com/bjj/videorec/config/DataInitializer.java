package com.bjj.videorec.config;

import com.bjj.videorec.model.User;
import com.bjj.videorec.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * Ensures a default user exists for PoC testing without full auth flow
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class DataInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {
        if (userRepository.findByUsername("poc_user").isEmpty()) {
            log.info("Creating default PoC user...");
            User user = new User();
            user.setUsername("poc_user");
            user.setEmail("poc@example.com");
            user.setPassword(passwordEncoder.encode("poc_password"));
            user.setRole(User.Role.USER);
            userRepository.save(user);
        }
    }
}
